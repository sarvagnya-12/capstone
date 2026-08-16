from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable


def read_rows(input_path: Path) -> Iterable[dict[str, Any]]:
    if input_path.is_dir():
        for file_path in sorted(input_path.rglob("*")):
            if file_path.suffix.lower() in {".csv", ".json", ".jsonl"}:
                yield from read_rows(file_path)
        return
    suffix = input_path.suffix.lower()
    if suffix == ".csv":
        with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
            yield from csv.DictReader(handle)
        return
    if suffix == ".jsonl":
        with input_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)
        return
    if suffix == ".json":
        data = json.loads(input_path.read_text(encoding="utf-8-sig"))
        if isinstance(data, list):
            for row in data:
                if isinstance(row, dict):
                    yield row
        elif isinstance(data, dict):
            for row in data.get("product_intelligence", data.get("items", [])):
                if isinstance(row, dict):
                    yield row
        return
    raise ValueError(f"Unsupported product intelligence input format: {input_path}")


def first_value(row: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    normalized = {str(key).strip().lower(): value for key, value in row.items()}
    for alias in aliases:
        if alias in normalized and normalized[alias] not in (None, ""):
            return normalized[alias]
    return None


def as_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None

