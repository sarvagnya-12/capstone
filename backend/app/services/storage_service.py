import shutil
from pathlib import Path

from fastapi import UploadFile
from PIL import Image

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


def save_pil_image(image: Image.Image, subfolder: str, filename: str) -> str:
    """Save an in-memory PIL image (e.g. GAN output) under STORAGE_ROOT/<subfolder>/
    <filename>, returning the path relative to STORAGE_ROOT."""
    target_dir = Path(settings.STORAGE_ROOT) / subfolder
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename
    image.save(target_path, "JPEG", quality=95)
    return str(target_path.relative_to(Path(settings.STORAGE_ROOT))).replace("\\", "/")


def get_path(relative_path: str) -> Path:
    return Path(settings.STORAGE_ROOT) / relative_path
