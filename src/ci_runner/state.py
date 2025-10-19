"""Persist and retrieve runner state."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Optional


_LOGGER = logging.getLogger(__name__)


@dataclass
class RunnerState:
    last_commit: Optional[str]


def load_state(path: str) -> RunnerState:
    if not os.path.exists(path):
        _LOGGER.info("State file %s does not exist yet", path)
        return RunnerState(last_commit=None)

    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
            return RunnerState(last_commit=payload.get("last_commit"))
    except (OSError, json.JSONDecodeError) as exc:
        _LOGGER.warning("Failed to read state file %s: %s", path, exc)
        return RunnerState(last_commit=None)


def save_state(path: str, state: RunnerState) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {"last_commit": state.last_commit}
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    os.replace(tmp_path, path)
    _LOGGER.debug("State written to %s", path)
