"""Configuration helpers for the Kubernetes CI runner."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


class ConfigurationError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class RunnerSettings:
    repo: str
    branch: str
    image: str
    chart_path: str
    release: str
    cicd_namespace: str
    deploy_namespace: str
    interval: int
    git_token: Optional[str]
    registry_secret: Optional[str]
    state_path: str
    max_retries: int
    verify_ssl: bool


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ConfigurationError(f"Missing required environment variable: {name}")
    return value


def _get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    value_lower = value.strip().lower()
    if value_lower in {"1", "true", "yes", "on"}:
        return True
    if value_lower in {"0", "false", "no", "off"}:
        return False

    raise ConfigurationError(f"{name} must be a boolean value (true/false)")


def load_settings() -> RunnerSettings:
    """Load runner settings from environment variables."""

    interval_raw = os.getenv("INTERVAL", "300")
    try:
        interval = max(5, int(interval_raw))
    except ValueError as exc:
        raise ConfigurationError("INTERVAL must be an integer") from exc

    max_retries_raw = os.getenv("MAX_RETRIES", "3")
    try:
        max_retries = max(1, int(max_retries_raw))
    except ValueError as exc:
        raise ConfigurationError("MAX_RETRIES must be an integer") from exc

    return RunnerSettings(
        repo=_require("REPO"),
        branch=os.getenv("BRANCH", "main"),
        image=_require("IMAGE"),
        chart_path=_require("CHART_PATH"),
        release=_require("RELEASE"),
        cicd_namespace=os.getenv("CICD_NS", "cicd"),
        deploy_namespace=os.getenv("DEPLOY_NS", "default"),
        interval=interval,
        git_token=os.getenv("GIT_TOKEN"),
        registry_secret=os.getenv("REGISTRY_SECRET"),
        state_path=os.getenv("STATE_PATH", "/data/runner-state.json"),
        max_retries=max_retries,
        verify_ssl=_get_bool("VERIFY_SSL", default=True),
    )
