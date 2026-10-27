#!/usr/bin/env python
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "typer",
# ]
# ///


import json
import logging
import pathlib
import subprocess
from typing import Annotated

import typer

logger = logging.getLogger(__name__)

app = typer.Typer()


def run_pass_cli(*args: str) -> dict:
    result = subprocess.run(
        ["pass-cli", *args, "--output", "json"],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def get_vault_id(name: str) -> str:
    """
    Get the vault ID for a given name using the `pass-cli` command-line tool.

    Args:
        name (str): The name of the vault to retrieve the ID for.
    """
    vaults = run_pass_cli("vault", "list")["vaults"]
    for vault in vaults:
        if vault["name"] == name:
            logger.debug(f"Found vault {name!r} with ID {vault['share_id']!r}")
            return vault["share_id"]
    raise ValueError(f"vault {name!r} not found")


def get_item_id(vault_id: str, item_name: str) -> str:
    """
    Get the item ID for a given vault ID and item name using the `pass-cli` command-line tool.

    Args:
        vault_id (str): The ID of the vault containing the item.
        item_name (str): The name of the item to retrieve the ID for.
    """
    items = run_pass_cli("item", "list", f"--share-id={vault_id}")["items"]
    for item in items:
        if item["title"] == item_name:
            logger.debug(f"Found item {item_name!r} with ID {item['id']!r} in vault {vault_id!r}")
            return item["id"]
    raise ValueError(f"item {item_name!r} not found in vault {vault_id!r}")


def get_attachment_id(vault_id: str, item_id: str) -> str:
    """
    Get the ID of the single attachment of a given item using the `pass-cli` command-line tool.

    Args:
        vault_id (str): The ID of the vault containing the item.
        item_id (str): The ID of the item containing the attachment.
    """
    attachments = run_pass_cli(
        "item", "view", f"--share-id={vault_id}", f"--item-id={item_id}"
    )["attachments"]
    if len(attachments) != 1:
        raise ValueError(
            f"expected exactly one attachment in item {item_id!r} of vault {vault_id!r}, found {len(attachments)}"
        )
    logger.debug(f"Found attachment {attachments[0]['content']['name']!r} with ID {attachments[0]['id']!r} in item {item_id!r} of vault {vault_id!r}")
    return attachments[0]["id"]


def download_kubeconfig(
    vault_id: str, item_id: str, attachment_id: str, output_path: pathlib.Path
) -> None:
    """
    Download a kubeconfig file from a vault and save it to the specified output path.

    Args:
        vault_id (str): The ID of the vault containing the kubeconfig item.
        item_id (str): The ID of the kubeconfig item to download.
        attachment_id (str): The ID of the attachment to download.
        output_path (pathlib.Path): The path where the kubeconfig file will be saved.
    """
    logger.debug(f"Downloading kubeconfig from vault {vault_id!r}, item {item_id!r}, attachment {attachment_id!r}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "pass-cli",
            "item",
            "attachment",
            "download",
            f"--share-id={vault_id}",
            f"--item-id={item_id}",
            f"--attachment-id={attachment_id}",
            f"--output={output_path}",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    output_path.chmod(0o600)
    logger.info(f"Downloaded kubeconfig to {str(output_path)!r}")


@app.command(no_args_is_help=True)
def main(
    project: Annotated[
        str,
        typer.Option(
            "--project",
            "-p",
            envvar="CICD_PROJECT",
            help="Name of the project containing the kubeconfig.",
        ),
    ],
    environment: Annotated[
        str,
        typer.Option(
            "--environment",
            "-e",
            envvar="CICD_ENVIRONMENT",
            help="Name of the kubernetes environment to download.",
        ),
    ],
    output_path: Annotated[
        pathlib.Path | None,
        typer.Option(
            "--output-path", "-o", envvar="CICD_OUTPUT_PATH", help="Path where the kubeconfig file will be saved."
        ),
    ] = None,
):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if output_path is None:
        output_path = pathlib.Path(f"local.{environment.replace(' ', '_')}.kubeconfig.yaml")
    try:
        logged_in = subprocess.run(["pass-cli", "info"], capture_output=True, text=True, check=False)
        if logged_in.returncode != 0:
            logger.error(
                "You are not logged in to pass-cli. Please log in with 'pass-cli login' and try again."
            )
            raise typer.Exit(1)
        logger.info(f"Downloading kubeconfig for project {project!r} and environment {environment!r} to {str(output_path)!r}")
        vault_id = get_vault_id(project)
        item_id = get_item_id(vault_id, environment)
        attachment_id = get_attachment_id(vault_id, item_id)
        download_kubeconfig(vault_id, item_id, attachment_id, output_path)
    except FileNotFoundError as e:
        if e.filename != "pass-cli":
            raise
        logger.error("pass-cli is not installed or not on PATH.")
        raise typer.Exit(1)
    except subprocess.CalledProcessError as e:
        logger.error(f"pass-cli failed: {(e.stderr or '').strip() or e}")
        raise typer.Exit(1)
    except ValueError as e:
        logger.error(str(e))
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
