"""Helpers to interact with the GitHub API."""
from __future__ import annotations

import logging
from typing import Optional

import requests
import urllib3


_LOGGER = logging.getLogger(__name__)
_API_BASE = "https://api.github.com"


class GitHubError(RuntimeError):
    """Raised when the GitHub API returns an unexpected response."""


class GitHubClient:
    """A very small wrapper around the GitHub REST API."""

    def __init__(
        self, repo: str, token: Optional[str] = None, *, verify_ssl: bool = True
    ) -> None:
        self._repo = repo
        self._token = token
        self._verify_ssl = verify_ssl
        if not verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            _LOGGER.warning("SSL verification is disabled for GitHub HTTP requests")

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def get_latest_commit(self, branch: str) -> str:
        """Return the SHA of the latest commit on ``branch``."""

        url = f"{_API_BASE}/repos/{self._repo}/commits/{branch}"
        response = requests.get(
            url, headers=self._headers(), timeout=30, verify=self._verify_ssl
        )
        if response.status_code != 200:
            raise GitHubError(
                f"Failed to fetch commit for {self._repo}@{branch}: {response.status_code}"
            )
        payload = response.json()
        sha = payload.get("sha")
        if not sha:
            raise GitHubError("GitHub response did not include a commit SHA")
        _LOGGER.debug("Latest commit on %s@%s is %s", self._repo, branch, sha)
        return sha

    def get_archive_url(self, ref: str) -> str:
        """Return the tarball URL for the repository at ``ref``."""

        return f"https://github.com/{self._repo}/archive/{ref}.tar.gz"
