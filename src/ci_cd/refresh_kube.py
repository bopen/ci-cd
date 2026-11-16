#!/usr/bin/env python
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "typer",
# ]
# ///

"""Refresh a Rancher kubeconfig in Proton Pass in one command."""

import logging
import pathlib
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Annotated

import typer

from ci_cd.get_kube_rancher import (
    ENVIRONMENTS as RANCHER_ENVIRONMENTS,
    Environment,
    RancherError,
    generate_kubeconfig,
    get_cluster,
    get_token,
)
from ci_cd.put_kube import get_item_id, get_vault_id, run_proton_cli, update_item_attach

logger = logging.getLogger(__name__)

app = typer.Typer()


class PipelineError(RuntimeError):
    """Raised when the refresh pipeline cannot proceed."""


@dataclass(frozen=True)
class ProtonConfig:
    """Proton Pass settings for one environment."""

    vault: str
    attachment: str


# Proton Pass defaults per environment. The item is always named like the
# cluster; fill in the shared vault name (or pass --project / CICD_PROJECT).
PROTON_ENVIRONMENTS: dict[str, ProtonConfig] = {
    "dev": ProtonConfig(vault="edh", attachment="kubeconfig.yaml"),
    "e2e": ProtonConfig(vault="edh", attachment="kubeconfig.yaml"),
    "prod": ProtonConfig(vault="edh", attachment="kubeconfig.yaml"),
}


def write_local_copy(source: pathlib.Path, output_path: pathlib.Path) -> None:
    """Write the generated kubeconfig to a local file with mode 0600.

    Args:
        source: Temporary file containing the generated kubeconfig.
        output_path: Destination path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(source.read_bytes())
    output_path.chmod(0o600)
    logger.info(f"Saved generated kubeconfig to {str(output_path)!r}")


def verify_kubeconfig(kubeconfig_path: pathlib.Path) -> None:
    """Check that the generated kubeconfig can reach the cluster.

    Args:
        kubeconfig_path: Path to the generated kubeconfig.

    Raises:
        PipelineError: If kubectl cannot use the kubeconfig.
    """
    logger.info("Validating the generated kubeconfig with kubectl")
    try:
        result = subprocess.run(
            ["kubectl", "--kubeconfig", str(kubeconfig_path), "get", "--raw=/version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise PipelineError(
            f"generated kubeconfig cannot reach the cluster: {detail or exc}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise PipelineError("timed out while validating the generated kubeconfig") from exc
    logger.debug(f"Cluster reports: {result.stdout.strip()}")


def verify_uploaded_attachment(
    item_id: str, attachment_name: str, expected_path: pathlib.Path
) -> None:
    """Download the uploaded attachment and compare it with the local file.

    Args:
        item_id: Proton Pass item ID.
        attachment_name: Name of the attachment to download.
        expected_path: Local file the remote attachment must match.

    Raises:
        PipelineError: If the remote attachment cannot be downloaded or differs.
    """
    with tempfile.TemporaryDirectory(prefix="refresh-kube-verify-") as tmp:
        downloaded = pathlib.Path(tmp) / attachment_name
        try:
            subprocess.run(
                [
                    "proton",
                    "pass",
                    "items",
                    "attachments",
                    "download",
                    item_id,
                    attachment_name,
                    "--dest",
                    str(downloaded),
                    "--force",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "").strip()
            raise PipelineError(
                f"could not download the uploaded attachment back: {detail or exc}"
            ) from exc
        if downloaded.read_bytes() != expected_path.read_bytes():
            raise PipelineError("uploaded attachment does not match the generated kubeconfig")
    logger.info(f"Verified attachment {attachment_name!r} on item {item_id!r}")


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
    project: Annotated[
        str | None,
        typer.Option(
            "--project",
            "-p",
            envvar="CICD_PROJECT",
            help="Proton Pass vault containing the kubeconfig item.",
        ),
    ] = None,
    attachment: Annotated[
        str | None,
        typer.Option(
            "--attachment",
            envvar="CICD_ATTACHMENT",
            help="Name of the Proton Pass attachment to replace.",
        ),
    ] = None,
    output_path: Annotated[
        pathlib.Path | None,
        typer.Option(
            "--output-path",
            "-o",
            envvar="CICD_OUTPUT_PATH",
            help="Path where the generated kubeconfig will be saved locally.",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Generate and validate the kubeconfig without uploading it.",
        ),
    ] = False,
    verify: Annotated[
        bool,
        typer.Option(
            "--verify/--no-verify",
            help="Validate the kubeconfig and verify the uploaded attachment.",
        ),
    ] = True,
) -> None:
    """Generate a kubeconfig from Rancher and publish it to Proton Pass."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        rancher_config = RANCHER_ENVIRONMENTS[environment.value]
        proton_config = PROTON_ENVIRONMENTS[environment.value]
        vault = project or proton_config.vault
        attachment_name = attachment or proton_config.attachment
        if not vault:
            raise PipelineError(
                f"no Proton Pass vault configured for environment {environment.value!r}; "
                "set it in PROTON_ENVIRONMENTS or pass --project"
            )
        if not attachment_name:
            raise PipelineError(
                f"no attachment name configured for environment {environment.value!r}"
            )
        if shutil.which("proton") is None:
            raise PipelineError("proton CLI is not installed or not on PATH")
        if verify and shutil.which("kubectl") is None:
            raise PipelineError(
                "kubectl is not installed or not on PATH; install it or pass --no-verify"
            )
        if output_path is None:
            output_path = pathlib.Path(f"local.{rancher_config.cluster}.kubeconfig.yaml")

        logger.info("Checking the Proton Pass session")
        run_proton_cli("account", "get")
        vault_id = get_vault_id(vault)
        item_id = get_item_id(vault, vault_id, rancher_config.cluster)
        logger.info(f"Found item {rancher_config.cluster!r} in vault {vault!r}")

        token = get_token(rancher_config)
        rancher_url = rancher_config.rancher_url.rstrip("/")
        logger.info(
            f"Generating kubeconfig for cluster {rancher_config.cluster!r} "
            f"from {rancher_url!r}"
        )
        cluster = get_cluster(rancher_url, token, rancher_config.cluster)
        kubeconfig = generate_kubeconfig(rancher_url, token, cluster)

        with tempfile.TemporaryDirectory(prefix="refresh-kube-") as tmp:
            upload_path = pathlib.Path(tmp) / attachment_name
            upload_path.write_text(kubeconfig)
            upload_path.chmod(0o600)
            if verify:
                verify_kubeconfig(upload_path)
            write_local_copy(upload_path, output_path)
            if dry_run:
                logger.info(
                    f"Dry run: would replace attachment {attachment_name!r} "
                    f"on item {rancher_config.cluster!r}"
                )
                return
            logger.info(
                f"Uploading kubeconfig to Proton Pass item {rancher_config.cluster!r}"
            )
            update_item_attach(item_id, upload_path)
            if verify:
                verify_uploaded_attachment(item_id, attachment_name, upload_path)
        logger.info("Kubeconfig refreshed successfully")
    except (PipelineError, RancherError) as exc:
        logger.error(str(exc))
        raise typer.Exit(1)
    except FileNotFoundError as exc:
        logger.error(f"required command not found: {exc.filename or exc}")
        raise typer.Exit(1)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip()
        logger.error(f"command failed ({exc.cmd}): {detail or exc}")
        raise typer.Exit(1)
    except subprocess.TimeoutExpired as exc:
        logger.error(f"command timed out: {exc.cmd}")
        raise typer.Exit(1)
    except (LookupError, KeyError, ValueError) as exc:
        logger.error(str(exc))
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
