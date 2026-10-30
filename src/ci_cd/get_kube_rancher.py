#!/usr/bin/env python
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "typer",
# ]
# ///

"""Download the kubeconfig of a cluster managed by Rancher."""

import json
import logging
import os
import pathlib
import urllib.error
import urllib.request
from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Any
from urllib.parse import urljoin

import typer

logger = logging.getLogger(__name__)

app = typer.Typer()

API_VERSION = "v3"
REQUEST_TIMEOUT_SECONDS = 30


class Environment(str, Enum):
    """Environments with Rancher defaults configured in this script."""

    dev = "dev"
    e2e = "e2e"
    prod = "prod"


@dataclass(frozen=True)
class EnvironmentConfig:
    """Default Rancher settings for one environment."""

    rancher_url: str
    cluster: str
    token_env: str


# Defaults per environment. Fill in the Rancher URL and the cluster ID (or
# name) of each instance. Secrets are never hardcoded: the token is read from
# the environment variable named by token_env, falling back to RANCHER_TOKEN.
ENVIRONMENTS: dict[str, EnvironmentConfig] = {
    "dev": EnvironmentConfig(
        rancher_url="https://rancher.dev.desp.space/",
        cluster="desp-dev",
        token_env="RANCHER_TOKEN_DEV",
    ),
    "e2e": EnvironmentConfig(
        rancher_url="https://rancher.e2e3.desp.space/",
        cluster="desp-e2e3",
        token_env="RANCHER_TOKEN_E2E",
    ),
    "prod": EnvironmentConfig(
        rancher_url="https://rancher.prod.desp.space/",
        cluster="desp-prod",
        token_env="RANCHER_TOKEN_PROD",
    ),
}


class RancherError(RuntimeError):
    """Raised when the Rancher API cannot be used."""


def api_error_message(exc: urllib.error.HTTPError) -> str:
    """Extract a readable message from a Rancher error response.

    Args:
        exc: The HTTP error raised by urllib.
    """
    body = exc.read().decode("utf-8", errors="replace").strip()
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return body or str(exc.reason)
    if isinstance(payload, dict):
        return str(payload.get("message") or payload.get("error") or body)
    return body


def call_api(
    url: str,
    token: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call the Rancher API and return the decoded JSON response.

    Args:
        url: Absolute URL to call.
        token: Rancher bearer token (``access_key:secret_key``).
        method: HTTP method to use.
        payload: Optional JSON body.

    Raises:
        RancherError: If the request fails or the response is not JSON.
    """
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Accept", "application/json")
    request.add_header("User-Agent", "ci-cd-get-kube-rancher")
    if data is not None:
        request.add_header("Content-Type", "application/json")

    logger.debug(f"{method} {url}")
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        message = api_error_message(exc)
        if exc.code == 401:
            message += " (check that the Rancher token is valid and not expired)"
        raise RancherError(f"{method} {url} failed with HTTP {exc.code}: {message}") from exc
    except urllib.error.URLError as exc:
        raise RancherError(f"cannot reach {url}: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RancherError(f"{method} {url} returned an invalid JSON response") from exc


def get_token(config: EnvironmentConfig) -> str:
    """Return the Rancher token for an environment.

    The environment-specific variable takes precedence over ``RANCHER_TOKEN``.

    Args:
        config: Environment configuration holding the token variable name.

    Raises:
        RancherError: If no token is set.
    """
    for name in (config.token_env, "RANCHER_TOKEN"):
        value = os.environ.get(name, "").strip()
        if value:
            logger.debug(f"Using Rancher token from {name}")
            return value
    raise RancherError(f"no Rancher token found; set {config.token_env} or RANCHER_TOKEN")


def get_cluster(rancher_url: str, token: str, selector: str) -> dict[str, Any]:
    """Find a cluster by ID, falling back to an exact name match.

    Args:
        rancher_url: Base URL of the Rancher instance.
        token: Rancher bearer token.
        selector: Cluster ID (``c-...``) or cluster name.

    Raises:
        RancherError: If the cluster is missing or the name is ambiguous.
    """
    clusters = call_api(f"{rancher_url}/{API_VERSION}/clusters", token).get("data", [])
    for cluster in clusters:
        if cluster.get("id") == selector:
            return cluster

    matches = [cluster for cluster in clusters if cluster.get("name") == selector]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        ids = ", ".join(str(cluster.get("id")) for cluster in matches)
        raise RancherError(f"cluster name {selector!r} is ambiguous; matching IDs: {ids}")

    available = ", ".join(
        sorted(f"{cluster.get('name')} ({cluster.get('id')})" for cluster in clusters)
    )
    raise RancherError(f"cluster {selector!r} not found; available clusters: {available or 'none'}")


def generate_kubeconfig(rancher_url: str, token: str, cluster: dict[str, Any]) -> str:
    """Ask Rancher to generate the kubeconfig of a cluster.

    Args:
        rancher_url: Base URL of the Rancher instance.
        token: Rancher bearer token.
        cluster: Cluster resource returned by the Rancher API.

    Raises:
        RancherError: If the action is unavailable or returns no kubeconfig.
    """
    action = cluster.get("actions", {}).get("generateKubeconfig")
    if not action:
        raise RancherError(
            f"cluster {cluster.get('name')!r} ({cluster.get('id')!r}) does not offer "
            f"generateKubeconfig (state: {cluster.get('state')!r})"
        )
    action_url = urljoin(f"{rancher_url}/", action)
    response = call_api(action_url, token, method="POST")
    kubeconfig = response.get("config")
    if not kubeconfig:
        raise RancherError("Rancher did not return a kubeconfig")
    return kubeconfig


def write_kubeconfig(kubeconfig: str, output_path: pathlib.Path) -> None:
    """Write a kubeconfig to disk with owner-only permissions.

    Args:
        kubeconfig: Kubeconfig file content.
        output_path: Destination path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(kubeconfig)
    output_path.chmod(0o600)
    logger.info(f"Downloaded kubeconfig to {str(output_path)!r}")


@app.command(no_args_is_help=True)
def main(
    environment: Annotated[
        Environment,
        typer.Option(
            "--environment",
            "-e",
            envvar="CICD_ENVIRONMENT",
            help="Target environment: dev, e2e or prod.",
        ),
    ],
    cluster: Annotated[
        str | None,
        typer.Option(
            "--cluster",
            "-c",
            envvar="CICD_RANCHER_CLUSTER",
            help="Cluster ID or name. Defaults to the value configured for the environment.",
        ),
    ] = None,
    rancher_url: Annotated[
        str | None,
        typer.Option(
            "--rancher-url",
            "-u",
            envvar="CICD_RANCHER_URL",
            help="Rancher URL. Defaults to the value configured for the environment.",
        ),
    ] = None,
    output_path: Annotated[
        pathlib.Path | None,
        typer.Option(
            "--output-path",
            "-o",
            envvar="CICD_OUTPUT_PATH",
            help="Path where the kubeconfig file will be saved.",
        ),
    ] = None,
) -> None:
    """Download the kubeconfig of a Rancher-managed cluster."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        config = ENVIRONMENTS[environment.value]
        target_url = (rancher_url or config.rancher_url).rstrip("/")
        target_cluster = cluster or config.cluster
        if not target_url:
            raise RancherError(
                f"no Rancher URL configured for environment {environment.value!r}; "
                "set it in ENVIRONMENTS or pass --rancher-url"
            )
        if not target_cluster:
            raise RancherError(
                f"no cluster configured for environment {environment.value!r}; "
                "set it in ENVIRONMENTS or pass --cluster"
            )
        if output_path is None:
            output_path = pathlib.Path(
                f"local.{target_cluster.replace(' ', '_')}.kubeconfig.yaml"
            )

        token = get_token(config)
        logger.info(
            f"Downloading kubeconfig for environment {environment.value!r} from "
            f"{target_url!r} to {str(output_path)!r}"
        )
        selected = get_cluster(target_url, token, target_cluster)
        logger.debug(f"Using cluster {selected.get('name')!r} ({selected.get('id')!r})")
        kubeconfig = generate_kubeconfig(target_url, token, selected)
        write_kubeconfig(kubeconfig, output_path)
    except RancherError as exc:
        logger.error(str(exc))
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
