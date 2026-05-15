# ci-cd

## git-clone Action

A GitHub Action that clones multiple git repositories with specific features.

### Usage

This action can be used in other repositories' workflows to clone multiple repositories with branch/tag selection support.

**Inputs:**
- **`repo-list`** (required): Space-separated list of repositories in `org/repo` format to clone
- **`git-pat`** (optional): Git Personal Access Token for authentication

**Example workflow:**

~~~yaml
- uses: bopen/ci-cd/git-clone
  env:
    REPO1_REF: "main"
    REPO2_REF: "v1.0.0"
  with:
    repo-list: "org/repo1 org/repo2"
    git-pat: ${{ secrets.GIT_PAT }}
~~~

### Features

- Clones multiple repositories in a single action step
- Supports branch/tag selection per repo via environment variables (e.g., `REPO_NAME_REF`)
- Handles authentication via PAT

## setup-deploy Action

A GitHub Action that sets up a deployment repository by cloning the repository itself and all its dependencies.

### Usage

This action can be used in workflows to prepare a deployment environment by cloning the main repository and its dependencies.

**Inputs:**
- **`repo`** (required): The main repository in `org/repo` format to clone
- **`deps-list`** (required): Space-separated list of dependencies in `org/repo` format to clone alongside the main repository
- **`deps-version-file`** (required): Path to a file containing the versions of the dependencies to clone
- **`git-pat`** (optional): Git Personal Access Token for authentication

**Example workflow:**
~~~yaml
  - uses: bopen/ci-cd/setup-deploy@main
    with:
      repo: org/main-repo
      deps-list: "org/dependency1 org/dependency2"
      deps-version-file: org/main-repo/environment.release
      git-pat: ${{ secrets.GIT_PAT }}
~~~

## update-dependency-file Action

A GitHub Action that updates a dependency file with the specified version of specified dependency.

### Usage

This action can be used in workflows to update a dependency file with the new version of a specified dependency.

**Inputs:**
- **`package-ref`** (required): The reference to the package in the dependency file
- **`version`** (required): The version to update the dependency to
- **`environment-file`** (required): The file containing the dependency information
