from __future__ import annotations

import shutil
import time
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from asset_manager.config import DownloadConfig
from shared.exceptions import ImageDownloadError
from shared.io import ensure_dir


class ImageDownloader:
    def __init__(self, config: DownloadConfig) -> None:
        self.config = config

    def fetch(self, url_or_path: str, destination: Path) -> Path:
        ensure_dir(destination.parent)
        parsed = urlparse(url_or_path)
        if parsed.scheme in {"http", "https"}:
            return self._download(url_or_path, destination)
        source_path = Path(url_or_path)
        if not source_path.exists():
            raise ImageDownloadError(f"Image source does not exist: {url_or_path}")
        shutil.copy2(source_path, destination)
        return destination

    def _download(self, url: str, destination: Path) -> Path:
        last_error: Exception | None = None
        for attempt in range(self.config.retries + 1):
            try:
                request = Request(url, headers={"User-Agent": self.config.user_agent})
                with urlopen(request, timeout=self.config.timeout_seconds) as response:
                    destination.write_bytes(response.read())
                return destination
            except (OSError, URLError) as exc:
                last_error = exc
                if attempt < self.config.retries:
                    time.sleep(0.25)
        raise ImageDownloadError(f"Could not download image {url}: {last_error}")

