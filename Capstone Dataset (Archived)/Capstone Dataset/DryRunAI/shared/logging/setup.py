from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from shared.io.files import ensure_dir
from shared.utils.time import utc_now_iso


class StructuredJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": utc_now_iso(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key.startswith("dryrun_"):
                payload[key.removeprefix("dryrun_")] = value
        return json.dumps(payload, ensure_ascii=True)


def configure_service_logging(
    service_name: str,
    logs_dir: Path,
    max_bytes: int,
    backup_count: int,
    console: bool = True,
) -> Path:
    ensure_dir(logs_dir)
    log_path = logs_dir / f"{service_name}.jsonl"
    logger = logging.getLogger()
    logger.handlers.clear()
    logger.setLevel(logging.INFO)

    file_handler = RotatingFileHandler(log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
    file_handler.setFormatter(StructuredJsonFormatter())
    logger.addHandler(file_handler)

    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        logger.addHandler(console_handler)

    return log_path

