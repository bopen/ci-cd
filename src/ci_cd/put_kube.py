#!/usr/bin/env python
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "typer",
# ]
# ///

import json
import subprocess
import typer
import os
import pathlib
import logging
from typing import Annotated

app = typer.Typer()
logger = logging.getLogger(__name__)

def run_proton_cli(*args: str) -> dict:
    """Run Proton CLI with JSON output and return the decoded response."""
    result = subprocess.run(
        ["proton", *args, "--output", "json"],
        stdout=subprocess.PIPE,
        check=True,
        text=True
    )
    return json.loads(result.stdout)

def check_connection() -> bool:
    """Check that the Proton CLI account is accessible.

    Returns:
        True when Proton returns the account information.

    Raises:
        subprocess.CalledProcessError: If the Proton command fails.
    """
    connected = run_proton_cli("account", "get")

def get_vault_id(vault: str) -> str:
    """Return the share ID for the named Proton Pass vault.

    Args:
        vault: Name of the vault to look up.

    Raises:
        LookupError: If Proton returns a vault with a different name.
        KeyError: If the response does not contain the expected fields.
    """
    result = run_proton_cli("pass", "vaults", "get", vault)
    if result["name"] != vault:
        raise LookupError(f"Expected vault {vault!r}, got {result['name']!r}")
    return result["share_id"]

def get_item_id(project: str, vault_id: str, item: str) -> str:
    """Return the ID of an item with the given name in a vault.

    Args:
        vault: Share ID of the vault containing the item.
        item: Name of the item to find.

    Raises:
        LookupError: If no item with that name exists in the vault.
    """
    result = run_proton_cli("pass", "items", "list", "--vault", vault_id, "--limit", "0")
    for entry in result["items"]:
        if entry["name"] == item:
            return entry["item_id"]
    raise LookupError(f"Item {item!r} not found in vault {project!r}")

def update_item_attach(item: str, attachment: str) -> dict:
    """Replace the matching remote attachment with a local file.

    Args:
        vault: Share ID of the vault containing the item.
        item: ID of the item to update.
        attachment: Path to the local file to upload. Its basename is used
            to identify the existing remote attachment to detach.

    Returns:
        The decoded JSON response from Proton.
    """
    filename = os.path.basename(attachment)
    return run_proton_cli(
        "pass", "items", "update", item,
        "--attach", attachment,
        "--detach", filename
    )

@app.command(help="Update a kubeconfig attachment on an existing Proton Pass item with a local file.", no_args_is_help=True)
def main(
    project: Annotated[
        str,
        typer.Option(help="Name of the project containing the kubeconfig.")
    ],
    environment: Annotated[
        str,
        typer.Option(help="Name of the kubernetes environment to update/upload.")
    ],
    path: Annotated[
        pathlib.Path,
        typer.Option(help="Path to the local Kubeconfig file to upload")
    ],
) -> None:
    """Replace an item's kubeconfig attachment in Proton Pass.

    Checks the Proton account connection, resolves the vault and item IDs,
    then uploads the local file and detaches the existing file with the same
    basename.
    """
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
    try:
        isconnected = check_connection()
        logger.info("You are logged in to Proton Pass.")
        vault_id = get_vault_id(project)
        logger.info("The Vault defined is corect")
        item_id = get_item_id(project, vault_id, environment)
        logger.info("The item you want to update exists in the correspondent project.")
        update = update_item_attach(item_id, path)
        logger.info("The attachment has been updated successfully")
    except FileNotFoundError as e:
        logger.error(str(e))
        raise typer.Exit(3)
    except subprocess.CalledProcessError as e:
        logger.error("The proton-cli command exited with error.")
        raise typer.Exit(1)
    except LookupError as e:
        logger.error(str(e))
        raise typer.Exit(5)


if __name__ == "__main__":
    app()
