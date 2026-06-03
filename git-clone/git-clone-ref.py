#!/usr/bin/env python
# /// script
# dependencies = [
#   "gitpython",
#   "typer",
# ]
# ///

import os
import logging
import shutil

import git
import typer

logger = logging.getLogger(__name__)

app = typer.Typer()


def git_clone_repo(
    repo_url: str,
    repo_path: str,
    repo_ref: str,
    multi_options: tuple[str, ...] = ("--depth=1", "--recurse-submodules"),
) -> str:
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
) -> None:
    for repo_path in paths:
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
        repo_ref = os.environ.get(repo_ref_env, "main")

        active_ref = git_clone_repo(repo_url, repo_path, repo_ref)
        logger.info(
            f"cloned repo {repo_name!r} ref {active_ref!r} " f"in path {repo_path!r}"
        )


@app.command()
def main(
    github_repos: list[str] = typer.Argument(..., help="GitHub repositories to clone"),
    git_pat: str = typer.Option(default="", envvar="GIT_PAT", help="GitHub Personal Access Token"),
):
    logging.basicConfig(level=logging.INFO)
    git_clone_repos(
        github_repos, "https://{credentials}github.com/{repo_org}/{repo_name}.git", git_pat
    )


if __name__ == "__main__":
    app()
