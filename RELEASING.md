# Releasing conda-meta-mcp

This document describes the release process for conda-meta-mcp on conda-forge.

## Prerequisites

- Maintainer access to the [conda-incubator/conda-meta-mcp](https://github.com/conda-incubator/conda-meta-mcp) repository
- GitHub account for conda-forge submission

## Version Management

This project uses [hatch-vcs](https://github.com/ofek/hatch-vcs) for version management. Versions are automatically derived from git tags.

## Release Steps

### 1. Create a GitHub Release

```bash
# Ensure you're on the main branch with the latest changes
git checkout main
git pull origin main

# Create an annotated tag (use semantic versioning)
git tag -a v0.1.0 -m "Release v0.1.0"

# Push the tag to GitHub
git push origin v0.1.0
```

Then create a GitHub Release from the tag via the GitHub UI or CLI:

```bash
gh release create v0.1.0 --title "v0.1.0" --notes "Release notes here"
```

### 2. Update conda-forge feedstock

After a new GitHub release, update the [conda-forge feedstock](https://github.com/conda-forge/conda-meta-mcp-feedstock):

1. Get the SHA256 of the release tarball:

   ```bash
   curl -sL https://github.com/conda-incubator/conda-meta-mcp/archive/refs/tags/v0.1.0.tar.gz | sha256sum
   ```

1. Fork the feedstock, update `recipe/meta.yaml` with the new version and SHA256, and open a PR.

Note: Since this package is not on PyPI, the conda-forge bot will not automatically detect new releases. You'll need to manually update the feedstock when creating new releases.

## Release Checklist

- [ ] All tests pass on CI
- [ ] CHANGELOG updated (if applicable)
- [ ] Version tag created and pushed
- [ ] GitHub Release created
- [ ] conda-forge recipe submitted/updated
- [ ] Documentation updated with new features

## Troubleshooting

### Build failures on conda-forge

If the conda-forge build fails:

1. Check the CI logs in the feedstock PR
1. Common issues:
   - Missing dependencies: Add them to `requirements/run`
   - Version conflicts: Adjust version pins
   - Import errors: Verify the package installs correctly

### Version not detected

If `hatch-vcs` doesn't detect the version:

1. Ensure you have a git tag: `git tag -l`
1. Make sure the tag follows semver: `v0.1.0`, `v1.0.0`, etc.
1. Verify hatch-vcs is configured in `pyproject.toml`

## Contact

For questions about the release process, open an issue on [GitHub](https://github.com/conda-incubator/conda-meta-mcp/issues).
