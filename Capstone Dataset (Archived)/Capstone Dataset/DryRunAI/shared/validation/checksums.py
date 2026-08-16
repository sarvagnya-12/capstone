from __future__ import annotations

from pathlib import Path

from shared.utils.hashing import sha256_file


def checksum_matches(path: Path, expected_sha256: str) -> bool:
    return sha256_file(path).lower() == expected_sha256.lower()

