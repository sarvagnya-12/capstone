import shutil
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings


def save_upload(file: UploadFile, subfolder: str) -> str:
    """Save an uploaded file under STORAGE_ROOT/<subfolder>/original<ext>, returning
    the path relative to STORAGE_ROOT (what gets persisted on the model).
    """
    target_dir = Path(settings.STORAGE_ROOT) / subfolder
    target_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(file.filename or "").suffix.lower()
    target_path = target_dir / f"original{suffix}"

    file.file.seek(0)
    with target_path.open("wb") as out_file:
        shutil.copyfileobj(file.file, out_file)

    return str(target_path.relative_to(Path(settings.STORAGE_ROOT))).replace("\\", "/")


def get_path(relative_path: str) -> Path:
    return Path(settings.STORAGE_ROOT) / relative_path
