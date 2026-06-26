#!/usr/bin/env python
# /// script
# dependencies = [
#   "gitpython",
#   "typer",
# ]
# ///

import logging
import os
import shutil
from typing import Annotated

import git
import tomllib
import typer

logger = logging.getLogger(__name__)

app = typer.Typer()


def git_clone_repo(
    repo_url: str,
    repo_path: str,
    repo_ref: str,
    multi_options: tuple[str, ...] = ("--depth=1", "--recurse-submodules"),
) -> str:
    if repo_ref:
        multi_options += (f"--branch {repo_ref}",)

    if os.path.exists(repo_path):
        logger.info(f"removing {repo_path!r}")
        shutil.rmtree(repo_path)

    repo = git.Repo.clone_from(repo_url, repo_path, multi_options=multi_options)

    try:
        return repo.active_branch.name
    except TypeError:
        return next((tag for tag in repo.tags if tag.commit == repo.head.commit)).name


def git_clone_repos(
    paths: list[str],
    repo_base_url_template: str,
    git_pat: str,
    default_repo_ref: str,
) -> None:
    if not paths:
        logger.warning("No repository to clone.")

    for repo_path in set(paths):
        repo_name = os.path.basename(repo_path)
        repo_org = os.path.basename(os.path.dirname(repo_path))
        git_pat_org = os.getenv(f"GIT_PAT_{repo_org.upper()}", git_pat)
        if git_pat_org:
            credentials = f"oauth2:{git_pat_org}@"
        else:
            credentials = ""
        repo_url = repo_base_url_template.format(
            credentials=credentials, repo_org=repo_org, repo_name=repo_name
        )
        print(repo_url)

        repo_ref_env = f"{repo_name}_REF".upper().replace("-", "_")
        repo_ref = os.environ.get(repo_ref_env, default_repo_ref)

        active_ref = git_clone_repo(repo_url, repo_path, repo_ref)
        logger.info(
            f"cloned repo {repo_name!r} ref {active_ref!r} in path {repo_path!r}"
        )


@app.command()
def main(
    repo_list: Annotated[
        list[str],
        typer.Argument(help="GitHub repositories to clone."),
    ] = [],
    git_pat: Annotated[
        str,
        typer.Option(envvar="GIT_PAT", help="GitHub Personal Access Token."),
    ] = "",
    default_repo_ref: Annotated[
        str,
        typer.Option(help="Default Git reference to check out."),
    ] = "main",
    pyproject_path: Annotated[
        str | None,
        typer.Option(help="Path to the pyproject.toml file."),
    ] = None,
):
    if pyproject_path:
        with open(pyproject_path, "rb") as fp:
            pyproject = tomllib.load(fp)
        config = pyproject.get("tool", {}).get("git-clone", {})
        repo_list.extend(config.get("repo-list", []))

    logging.basicConfig(level=logging.INFO)
    git_clone_repos(
        repo_list,
        "https://{credentials}github.com/{repo_org}/{repo_name}.git",
        git_pat,
        default_repo_ref,
    )


if __name__ == "__main__":
    app()
