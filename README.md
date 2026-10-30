# ci-cd

## git-clone Action

A GitHub Action that clones multiple git repositories with specific features.

### Usage

This action can be used in other repositories' workflows to clone multiple repositories with branch/tag selection support.

**Inputs:**
- **`repo-list`** (required): Space-separated list of repositories in `org/repo` format to clone
- **`git-pat`** (optional): Git Personal Access Token for authentication
- **`default-repo-ref`** (optional): Default Git reference to check out
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

## copy-git-clone-script Action

A GitHub Action that copies the `git-clone-ref.py` script into a directory of the calling repository.

### Usage

**Inputs:**
- **`target-path`** (required): The directory where `git-clone-ref.py` should be copied

**Example workflow:**
~~~yaml
  - name: Copy git clone script
    uses: bopen/ci-cd/copy-git-clone-script@main
    with:
      target-path: scripts
~~~

## Scripts

The scripts backing the actions live in `src/ci_cd` and are packaged as a uv project, so they can also be run locally:

- **`git-clone-ref`**: clones multiple repositories (used by the `git-clone` action)
- **`get-kube`**: downloads a kubeconfig from Proton Pass
- **`get-kube-rancher`**: downloads a kubeconfig from a Rancher-managed cluster
- **`put-kube`**: uploads a kubeconfig to a Proton Pass item, replacing the existing attachment with the same filename
- **`refresh-kube`**: generates a kubeconfig from Rancher and replaces the Proton Pass attachment in one command

### get-kube

Downloads the kubeconfig of a Kubernetes environment stored in Proton Pass, using the `pass-cli` command-line tool.

Each project is a Proton Pass vault, and each environment is an item in that vault with the kubeconfig as its only attachment.

**Requirements:**
- `pass-cli` installed and on `PATH`
- Logged in with `pass-cli login`

**Options:**
- **`-p, --project`** (required, env `CICD_PROJECT`): Name of the vault containing the kubeconfig
- **`-e, --environment`** (required, env `CICD_ENVIRONMENT`): Name of the item holding the kubeconfig
- **`-o, --output-path`** (optional, env `CICD_OUTPUT_PATH`): Where to save the kubeconfig. Defaults to `local.<environment>.kubeconfig.yaml` in the current directory, with spaces replaced by `_`

**Example:**
~~~bash
uv run get-kube -p my-project -e "production eu"
export KUBECONFIG=$PWD/local.production_eu.kubeconfig.yaml
~~~

The file is saved readable only by its owner (`0600`), since it contains cluster credentials. Running `uv run get-kube` with no arguments prints the help.

### get-kube-rancher

Downloads the kubeconfig of a cluster managed by Rancher, using the Rancher v3 API. Each environment (`dev`, `e2e`, `prod`) has defaults hardcoded in the `ENVIRONMENTS` mapping in `src/ci_cd/get_kube_rancher.py`: the Rancher URL, the cluster ID or name, and the environment variable that holds the token.

**Setup:**
- Fill in `rancher_url` and `cluster` for each environment in `ENVIRONMENTS`.
- Export the token for the environment (`RANCHER_TOKEN_DEV`, `RANCHER_TOKEN_E2E`, `RANCHER_TOKEN_PROD`), or use `RANCHER_TOKEN` as a fallback. Create it in Rancher under **Account & API Keys** and use the **Bearer Token** (`token-xxxxx:secret`).

**Options:**
- **`-e, --environment`** (required, env `CICD_ENVIRONMENT`): `dev`, `e2e` or `prod`
- **`-c, --cluster`** (optional, env `CICD_RANCHER_CLUSTER`): Cluster ID or name, overriding the environment default
- **`-u, --rancher-url`** (optional, env `CICD_RANCHER_URL`): Rancher URL, overriding the environment default
- **`-o, --output-path`** (optional, env `CICD_OUTPUT_PATH`): Where to save the kubeconfig. Defaults to `local.<cluster>.kubeconfig.yaml`.

**Example:**
~~~bash
export RANCHER_TOKEN_DEV='token-xxxxx:yyyyyyyy'
uv run get-kube-rancher -e dev
export KUBECONFIG=$PWD/local.desp-dev.kubeconfig.yaml
~~~

The file is saved readable only by its owner (`0600`). On Rancher 2.8 and later the token embedded in a generated kubeconfig expires after about 30 days, so regenerate it at the start of each pipeline run rather than storing it as a long-lived secret.

### put-kube

Uploads a local kubeconfig file to an existing Proton Pass item. The project is the vault name, and the environment is the item within that vault. The script replaces the remote attachment whose filename matches the uploaded file's basename.

**Requirements:**
- `proton` CLI installed and on `PATH`
- Logged in with `proton account login`

**Required options:**
- **`--project <TEXT>`**: Name of the project/vault containing the kubeconfig
- **`--environment <TEXT>`**: Name of the Kubernetes environment item to update
- **`--path <PATH>`**: Path to the local kubeconfig file to upload

**Example:**
~~~bash
uv run put-kube --project my-project --environment production --path ./kubeconfig.yaml
~~~

The existing attachment in the item must have the same filename as the local file, because the script uses the local file's basename to replace it. Running `uv run put-kube` without arguments displays the help. The command exits with a nonzero status if the file is missing, a Proton CLI command fails, or the project or environment cannot be found.

### refresh-kube

Admin pipeline that combines `get-kube-rancher` and `put-kube`: it generates a fresh kubeconfig from Rancher, validates it with `kubectl`, saves a local copy, and replaces the `kubeconfig.yaml` attachment of the matching Proton Pass item.

One environment maps to one cluster and one Proton Pass item:

| `--environment` | Rancher | Cluster and Proton item |
| --- | --- | --- |
| `dev` | `https://rancher.dev.desp.space` | `desp-dev` |
| `e2e` | `https://rancher.e2e3.desp.space` | `desp-e2e3` |
| `prod` | `https://rancher.prod.desp.space` | `desp-prod` |

The Rancher defaults come from `ENVIRONMENTS` in `src/ci_cd/get_kube_rancher.py`. The Proton Pass vault and attachment name are configured in `PROTON_ENVIRONMENTS` in `src/ci_cd/refresh_kube.py`; pass `--project` or set `CICD_PROJECT` until the vault is filled in there.

**Requirements:**
- `proton` CLI installed and on `PATH`, logged in with `proton account login`
- `kubectl` installed and on `PATH` unless `--no-verify` is used
- The Rancher token exported as `RANCHER_TOKEN_DEV`, `RANCHER_TOKEN_E2E` or `RANCHER_TOKEN_PROD`

**Options:**
- **`-e, --environment`** (required, env `CICD_ENVIRONMENT`): `dev`, `e2e` or `prod`
- **`-p, --project`** (optional, env `CICD_PROJECT`): Proton Pass vault containing the kubeconfig item; overrides `PROTON_ENVIRONMENTS`
- **`--attachment`** (optional, env `CICD_ATTACHMENT`): Attachment name to replace, defaults to `kubeconfig.yaml`
- **`-o, --output-path`** (optional, env `CICD_OUTPUT_PATH`): Local copy path, defaults to `local.<cluster>.kubeconfig.yaml`
- **`--dry-run`**: generate, validate and write the local copy without uploading
- **`--verify/--no-verify`**: validate the kubeconfig and confirm the uploaded attachment matches; enabled by default

**Example:**
~~~bash
export RANCHER_TOKEN_E2E='token-xxxxx:yyyyyyyy'
uv run refresh-kube -e e2e -p my-project
export KUBECONFIG=$PWD/local.desp-e2e3.kubeconfig.yaml
~~~

The command fails before uploading if the generated kubeconfig cannot reach the cluster, so a broken Rancher token does not replace a working credential. The local copy and the temporary upload file are both written with mode `0600`.

## License

```
Copyright 2026, B-Open Solutions srl.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```
