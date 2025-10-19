"""Helm helper utilities."""
from __future__ import annotations

import logging
import subprocess
from typing import Sequence

_LOGGER = logging.getLogger(__name__)


class HelmError(RuntimeError):
    """Raised when a Helm command fails."""


def _run_helm(args: Sequence[str]) -> None:
    command = ["helm", *args]
    _LOGGER.info("Executing: %s", " ".join(command))
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        _LOGGER.error("Helm command failed: %s", completed.stderr)
        raise HelmError(f"Helm command failed: {' '.join(command)}")
    if completed.stdout:
        _LOGGER.debug("Helm output: %s", completed.stdout)


def upgrade_release(
    release: str,
    chart_path: str,
    namespace: str,
    image: str,
    tag: str,
) -> None:
    args = [
        "upgrade",
        "--install",
        release,
        chart_path,
        "--namespace",
        namespace,
        "--create-namespace",
        "--atomic",
        "--set",
        f"image.repository={image}",
        "--set",
        f"image.tag={tag}",
    ]
    _run_helm(args)
