from __future__ import annotations

import os


def github_run_url(env: dict[str, str] | None = None) -> str | None:
    """Build a clickable GitHub Actions run URL from environment variables.

    Returns None when not running on GitHub Actions or when required variables
    are missing.
    """

    e = env if env is not None else os.environ
    server_url = e.get("GITHUB_SERVER_URL")
    repo = e.get("GITHUB_REPOSITORY")
    run_id = e.get("GITHUB_RUN_ID")
    if not server_url or not repo or not run_id:
        return None
    return f"{server_url}/{repo}/actions/runs/{run_id}"
