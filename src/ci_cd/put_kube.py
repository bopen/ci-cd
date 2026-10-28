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
from typing import Annotated

app = typer.Typer()

def run_proton_cli(*args: str) -> dict:
    """Run Proton CLI with JSON output and return the decoded response."""
    result = subprocess.run(
        ["proton", *args, "--output", "json"],
        stdout=subprocess.PIPE,
        check=True,
        text=True
    )
    return json.loads(result.stdout)

def print_status(step: str, status: bool) -> None:
    """Print the outcome of a named workflow step."""
    print("The step:", step, ",was executed with result:", status)

def check_connection() -> bool:
    """Check that the Proton CLI account is accessible.

    Returns:
        True when Proton returns the account information.

    Raises:
        subprocess.CalledProcessError: If the Proton command fails.
    """
    try:
        connected = run_proton_cli("account", "get")
        return True
    except Exception:
        print("Check connection Error - Please Login using 'proton account login' command!")
        raise

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

def get_item_id(vault: str, item: str) -> str:
    """Return the ID of an item with the given name in a vault.

    Args:
        vault: Share ID of the vault containing the item.
        item: Name of the item to find.

    Raises:
        LookupError: If no item with that name exists in the vault.
    """
    result = run_proton_cli("pass", "items", "list", "--vault", vault, "--limit", "0")
    for entry in result["items"]:
        if entry["name"] == item:
            return entry["item_id"]
    raise LookupError(f"Item {item!r} not found in vault {vault!r}")

def update_item_attach(vault: str, item: str, attachment: str) -> dict:
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
    print("Update", attachment, "using remote filename:", filename)
    return run_proton_cli(
        "pass", "items", "update", item,
        "--attach", attachment,
        "--detach", filename
    )

@app.command(help="Update a kubeconfig attachment on an existing Proton Pass item with a local file.")
def main(
    project: Annotated[
        str,
        typer.Option(help="Name of the project containing the kubeconfig.")
    ] = "Personal",
    environment: Annotated[
        str,
        typer.Option(help="Name of the kubernetes environment to update/upload.")
    ] = "kubeconfig",
    attach: Annotated[
        str,
        typer.Option(help="Path to the local file to upload")
    ] = "kubeconfig.yaml",
) -> None:
    """Replace an item's kubeconfig attachment in Proton Pass.

    Checks the Proton account connection, resolves the vault and item IDs,
    then uploads the local file and detaches the existing file with the same
    basename.
    """
    try:
        isconnected = check_connection()
        print_status("Test Connection", isconnected)
        vault_id = get_vault_id(project)
        print_status("Get Vault ID", vault_id)
        item_id = get_item_id(vault_id, environment)
        print_status("Get Item ID", item_id )
        update = update_item_attach(vault_id, item_id, attach)
        print_status("Update Attachment", update["action"])
    except Exception as e:
        import traceback
        print(f"EXCEPTION CAUGHT: {type(e).__name__}: {e!r}")
        traceback.print_exc()

if __name__ == "__main__":
    app()
