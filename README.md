# ci-cd

## git-clone Action

A GitHub Action that clones multiple git repositories with specific features.

### Usage

This action can be used in other repositories' workflows to clone multiple repositories with branch/tag selection support.

**Inputs:**
- **`repo-list`** (required): Space-separated list of repositories in `org/repo` format to clone
- **`git-pat`** (optional): Git Personal Access Token for authentication
- **`default-repo-ref`** (optional): Default Git reference to check out
- **`use-pyproject`** (optional): Whether to parse and use pyproject.toml configuration
- **`pyproject-path`** (optional): Path to the pyproject.toml file

**Example workflow:**

~~~yaml
- uses: bopen/ci-cd/git-clone
  env:
    REPO1_REF: "main"
    REPO2_REF: "v1.0.0"
  with:
    repo-list: "org/repo1 org/repo2"
    git-pat: ${{ secrets.GIT_PAT }}
    default-repo-ref: main
    use-pyproject: false
    pyproject-path: pyproject.toml
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
- **`deps-versions-file`** (required): Path to a file containing the versions of the dependencies to clone
- **`git-pat`** (optional): Git Personal Access Token for authentication

**Example workflow:**
~~~yaml
  - uses: bopen/ci-cd/setup-deploy@main
    with:
      repo: org/main-repo
      deps-list: "org/dependency1 org/dependency2"
      deps-versions-file: org/main-repo/environment.release
      git-pat: ${{ secrets.GIT_PAT }}
~~~

## update-dependency-file Action

A GitHub Action that updates a dependency file with the specified version of specified dependency.

### Usage

This action can be used in workflows to update a dependency file with the new version of a specified dependency.

**Inputs:**
- **`package-ref`** (required): The reference to the package in the dependency file
- **`version`** (required): The version to update the dependency to
- **`deps-versions-file`** (required): The file containing the dependency information

**Example workflow:**

~~~yaml
  - name: Update dependency file
    uses: bopen/ci-cd/update-dependency-file@main
    with:
      package-ref: PACKAGE_NAME_REF
      version: v1.0
      deps-versions-file: environment.release
~~~

## check-update-uv-lock Action

A GitHub Action that checks if the `uv.lock` file is up to date and updates it if necessary.

### Usage

This action can be used in workflows to ensure that the `uv.lock` file is correct and updated if needed.

**Inputs:**
- **`repo-path`** (required): The path to the repository containing the `uv.lock` file
**Outputs:**
- **`uv-lock`**: Boolean indicating whether the `uv.lock` file has been updated

**Example workflow:**
~~~yaml
  - name: Check and update uv lock
    id: check-update-uv-lock
    uses: bopen/ci-cd/check-update-uv-lock@main
    with:
      repo-path: path/to/repository
~~~