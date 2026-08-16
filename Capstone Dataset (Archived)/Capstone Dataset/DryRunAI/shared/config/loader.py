from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.io.files import read_json


def load_config(default_path: Path, override_path: Path | None = None) -> dict[str, Any]:
    config = read_json(default_path)
    if override_path and override_path.exists():
        config = deep_merge(config, read_json(override_path))
    return config


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged

