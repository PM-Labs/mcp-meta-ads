# Release Process

This repository uses GitHub Actions to automatically publish releases to PyPI. Here's how it works:

## Automated Publishing

### Setup Required

1. **Configure Trusted Publishing on PyPI** (Recommended):
   - Go to your PyPI project page: https://pypi.org/manage/project/meta-ads-mcp/
   - Navigate to "Publishing" → "Add a new pending publisher"
   - Fill in the details:
     - Owner: `nictuku` (your GitHub username/org)
     - Repository name: `meta-ads-mcp`
     - Workflow name: `publish.yml`
     - Environment name: `release`
   
   This eliminates the need for API tokens and is more secure.

2. **Alternative: API Token Method**:
   - If you prefer using API tokens, go to PyPI → Account Settings → API tokens
   - Create a token with scope limited to this project
   - Add it as a repository secret named `PYPI_API_TOKEN`
   - Modify `.github/workflows/publish.yml` to use the token instead of trusted publishing

### Creating a Release

1. **Update the version** in `pyproject.toml`:
   ```toml
   version = "0.3.8"  # Increment as needed
   ```

2. **Commit and push** the version change:
   ```bash
   git add pyproject.toml
   git commit -m "Bump version to 0.3.8"
   git push origin main
   ```

3. **Create a GitHub release**:
   - Go to https://github.com/nictuku/meta-ads-mcp/releases
   - Click "Create a new release"
   - Tag version: `v0.3.8` (must match the version in pyproject.toml)
   - Release title: `v0.3.8`
   - Add release notes describing what changed
   - Click "Publish release"

4. **Automatic deployment**:
   - The GitHub Action will automatically trigger
   - It will build the package and publish to PyPI
   - Check the "Actions" tab to monitor progress

## Workflows

### `publish.yml`
- **Triggers**: When a GitHub release is published
- **Purpose**: Builds and publishes the package to PyPI
- **Environment**: Uses the `release` environment for additional security

### `test.yml`
- **Triggers**: On pushes and pull requests to main/master
- **Purpose**: Tests package building and installation across Python versions
- **Matrix**: Tests Python 3.10, 3.11, and 3.12

## Manual Deployment

If you need to deploy manually:

```bash
# Install build tools
pip install build twine

# Build the package
python -m build

# Upload to PyPI (requires API token or configured credentials)
python -m twine upload dist/*
```

## Version Management

- Follow semantic versioning (SemVer): `MAJOR.MINOR.PATCH`
- Update version in `pyproject.toml` before creating releases
- The git tag should match the version (e.g., `v0.3.8` for version `0.3.8`)

## Security Notes

- Trusted publishing is preferred over API tokens
- The `release` environment can be configured with additional protection rules
- Only maintainers should be able to create releases
- All builds run in isolated GitHub-hosted runners 