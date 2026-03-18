# Git Workflow

## Branch Strategy

- Always work on feature branches, never commit directly to `main`
- Branch naming: `feature/<short-description>` or `fix/<short-description>`
- When work is ready to release, create a PR to merge into `main`

## Commit Regularly

- Commit changes to GitHub frequently — don't let work pile up locally
- After completing a meaningful unit of work (a task, a fix, a new file), commit and push
- Use clear, concise commit messages describing what changed

## Release Flow

- Merging a PR to `main` triggers automatic tagging and release via GitHub Actions
- The tag triggers publishing to PyPI so the package is available via `uvx`
- Always ensure the version in `pyproject.toml` is bumped before merging a release PR
