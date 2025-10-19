"""Utilities for downloading repository artifacts."""
from __future__ import annotations

import logging
import tarfile
import tempfile
from pathlib import Path
from typing import Optional, Tuple

import requests
import urllib3

_LOGGER = logging.getLogger(__name__)


class RepositoryError(RuntimeError):
    """Raised when the repository cannot be downloaded or unpacked."""


def download_and_extract(
    archive_url: str,
    *,
    verify_ssl: bool = True,
    ca_bundle_path: Optional[str] = None,
) -> Tuple[Path, tempfile.TemporaryDirectory]:
    """Download a tarball from ``archive_url`` and extract it to a temp directory."""

    verify_option = ca_bundle_path if verify_ssl and ca_bundle_path else verify_ssl

    if verify_option is False:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    response = requests.get(
        archive_url, stream=True, timeout=60, verify=verify_option
    )
    if response.status_code != 200:
        raise RepositoryError(
            f"Failed to download repository archive: {response.status_code}"
        )

    temp_dir = tempfile.TemporaryDirectory(prefix="repo-")
    tar_path = Path(temp_dir.name) / "repo.tar.gz"
    with tar_path.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                handle.write(chunk)

    with tarfile.open(tar_path, "r:gz") as archive:
        archive.extractall(temp_dir.name)

    # GitHub archives extract into a single top-level directory.
    root_dirs = list(Path(temp_dir.name).iterdir())
    if not root_dirs:
        raise RepositoryError("Archive did not contain any files")

    repo_root = root_dirs[0]
    _LOGGER.debug("Repository extracted to %s", repo_root)
    return repo_root, temp_dir
