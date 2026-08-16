from __future__ import annotations

from pathlib import Path


def find_project_root(start: Path) -> Path:
    for path in (start.resolve(), *start.resolve().parents):
        if (path / "schemas" / "products_schema.json").exists() and (path / "taxonomy").is_dir():
            return path
    raise FileNotFoundError(f"Could not locate DryRunAI project root from {start}")


def resolve_project_path(value: str | Path | None, default: Path, project_root: Path) -> Path:
    if value in (None, ""):
        return default
    path = Path(value)
    if path.is_absolute():
        return path
    return project_root / path


def next_version_dir(parent: Path, prefix: str = "catalog_v") -> tuple[Path, int]:
    parent.mkdir(parents=True, exist_ok=True)
    versions = []
    for path in parent.glob(f"{prefix}*"):
        suffix = path.name.removeprefix(prefix)
        if path.is_dir() and suffix.isdigit():
            versions.append(int(suffix))
    version = max(versions, default=0) + 1
    version_dir = parent / f"{prefix}{version}"
    version_dir.mkdir(parents=True, exist_ok=False)
    return version_dir, version

