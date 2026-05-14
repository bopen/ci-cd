# ci-cd

## git-clone Action

A GitHub Action that clones multiple git repositories with specific features.

### Usage

This action can be used in other repositories' workflows to clone multiple repositories with branch/tag selection support.

**Inputs:**
- **`repo-list`** (required): Space-separated list of repositories in `org/repo` format to clone
- **`git-pat`** (optional): Git Personal Access Token for authentication

**Example workflow:**

```yaml
- uses: bopen/ci-cd/git-clone
  env:
    REPO1_REF: "main"
    REPO2_REF: "v1.0.0"
  with:
    repo-list: "org/repo1 org/repo2"
    git-pat: ${{ secrets.GIT_PAT }}
```

### Features

- Clones multiple repositories in a single action step
- Supports branch/tag selection per repo via environment variables (e.g., `REPO_NAME_REF`)
- Handles authentication via PAT
