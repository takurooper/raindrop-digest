from __future__ import annotations

from raindrop_digest.runner_kit.gha import github_run_url


def test_github_run_url_builds_url_when_vars_present() -> None:
    env = {
        "GITHUB_SERVER_URL": "https://github.com",
        "GITHUB_REPOSITORY": "owner/repo",
        "GITHUB_RUN_ID": "123",
    }
    assert github_run_url(env) == "https://github.com/owner/repo/actions/runs/123"


def test_github_run_url_returns_none_when_missing() -> None:
    assert github_run_url({}) is None
