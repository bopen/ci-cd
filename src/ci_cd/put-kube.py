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
    result = subprocess.run(
        ["proton", *args, "--output", "json"],
        stdout=subprocess.PIPE,
        check=True,
        text=True
    )
    return json.loads(result.stdout)

def print_status(step: str, status: bool) -> None:
    print("The step:", step, ",was executed with result:", status)

def check_connection() -> bool:
    """
    Check if the user is already connected to proton
    """
    try:
        connected = run_proton_cli("account", "get")
        return True
    except Exception:
        print("Check connection Error - Please Login using 'proton account login' command!")
        raise

def get_vault_id(vault: str) -> str:
    result = run_proton_cli("pass", "vaults", "get", vault)
    if result["name"] != vault:
        raise LookupError(f"Expected vault 'edh', got {result['name']!r}")
    # print("trovato vault_id:", result["share_id"])
    return result["share_id"]

def get_item_id(vault: str, item: str) -> str:
    result = run_proton_cli("pass", "items", "list", "--vault", vault, "--limit", "0")
    for outem in result["items"]:
        if outem["name"] == item:
            # print("Trovato item_id:", outem["item_id"])
            return outem["item_id"]
    raise LookupError(f"Item {item!r} not found in vault {vault!r}")

def update_item_attach(item: str, attachment: str) -> dict:
    filename = os.path.basename(attachment)
    print("Update", filename, "using local filename:", attachment)
    return run_proton_cli(
        "pass", "items", "update", item,
        "--attach", attachment,
        "--detach", filename
    )

@app.command()
def main(
    project: Annotated[
        str,
        typer.Option(help="Name of the project containing the kubeconfig.")
    ] = "Personal",
    environment: Annotated[
        str,
        typer.Option(help="Name of the kubernetes environment to update/upload.")
    ] = "KubeTest",
    attach: Annotated[
        str,
        typer.Option(help="Local file path to be uploaded - file must be already in the attachments list")
    ] = "kubeconfig.yaml",
):
    try:
        isconnected = check_connection()
        print_status("Test Connection", isconnected)
        vault_id = get_vault_id(project)
        print_status("Get Vault ID", vault_id)
        item_id = get_item_id(vault_id, environment)
        print_status("Get Item ID", item_id )
        update = update_item_attach(item_id, attach)
        print_status("Update Attachment", update["action"])
    except Exception as e:
        import traceback
        print(f"EXCEPTION CAUGHT: {type(e).__name__}: {e!r}")
        traceback.print_exc()

if __name__ == "__main__":
    app()
