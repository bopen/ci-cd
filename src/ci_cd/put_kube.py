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
import pathlib
import logging
from typing import Annotated, Any

app = typer.Typer()
logger = logging.getLogger(__name__)

def run_proton_cli(*args: str) -> Any:
    """Run Proton CLI with JSON output and return the decoded response."""
    result = subprocess.run(
        ["proton", *args, "--output", "json"],
        capture_output=True,
        check=True,
        text=True
    )
    return json.loads(result.stdout)

def check_connection() -> None:
    """Check that the Proton CLI account is accessible.

    Raises:
        subprocess.CalledProcessError: If the Proton command fails.
    """
    run_proton_cli("account", "get")

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

def get_attachment_names(item: str) -> list[str]:
    """Return the names of the attachments currently on an item.

    Args:
        item: ID or name of the item to inspect.

    Returns:
        The attachment names, in the order Proton lists them.
    """
    result = run_proton_cli("pass", "items", "attachments", "list", item)
    attachments = result["attachments"] if isinstance(result, dict) else result
    return [entry["name"] for entry in attachments]

def update_item_attach(item: str, attachment: pathlib.Path) -> Any:
    """Replace the attachments on an item with a local file.

    Args:
        item: ID of the item to update.
        attachment: Path to the local file to upload.

    Returns:
        The decoded JSON response from Proton.
    """
    args = ["pass", "items", "update", item, "--attach", str(attachment)]
    for name in get_attachment_names(item):
        args.extend(["--detach", name])
    return run_proton_cli(*args)

@app.command(help="Update a kubeconfig attachment on an existing Proton Pass item with a local file.", no_args_is_help=True)
def main(
    project: Annotated[
        str,
        typer.Option(
            "--project",
            "-p",
            help="Name of the project containing the kubeconfig."
        )
    ],
    environment: Annotated[
        str,
        typer.Option(
            "--environment",
            "-e",
            help="Name of the kubernetes environment to update/upload."
        )
    ],
    path: Annotated[
        pathlib.Path,
        typer.Argument(help="Path to the local Kubeconfig file to upload")
    ],
) -> None:
    """Replace an item's kubeconfig attachment in Proton Pass.

    Checks the Proton account connection, resolves the vault and item IDs,
    then uploads the local file and detaches whatever the item already holds.
    """
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
    try:
        if not path.is_file():
            raise FileNotFoundError(f"Local file {str(path)!r} does not exist")
        check_connection()
        logger.info("You are logged in to Proton Pass.")
        vault_id = get_vault_id(project)
        logger.info("The Vault defined is corect")
        item_id = get_item_id(project, vault_id, environment)
        logger.info("The item you want to update exists in the correspondent project.")
        update_item_attach(item_id, path.absolute())
        logger.info("The attachment has been updated successfully")
    except FileNotFoundError as e:
        logger.error(str(e))
        raise typer.Exit(3)
    except subprocess.CalledProcessError as e:
        detail = (e.stderr or "").strip()
        logger.error(f"The proton-cli command exited with error: {detail or e}")
        raise typer.Exit(1)
    except LookupError as e:
        logger.error(str(e))
        raise typer.Exit(5)


if __name__ == "__main__":
    app()
