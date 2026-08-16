from pathlib import Path

from PIL import Image, ImageOps

from app.core.config import settings

# Fixed input resolution for the GAN pipeline. Set here and reused as-is when the
# pretrained StyleGAN2 checkpoint is loaded in Step 15, so the two never drift.
TARGET_SIZE = (256, 256)


def preprocess_image(original_relative_path: str, output_subfolder: str) -> str:
    """Resize/center-crop the image at STORAGE_ROOT/original_relative_path to
    TARGET_SIZE and normalize it to RGB, saving the result under
    STORAGE_ROOT/<output_subfolder>/preprocessed.jpg. Returns the path relative
    to STORAGE_ROOT (what gets persisted on the Product row).
    """
    source_path = Path(settings.STORAGE_ROOT) / original_relative_path

    with Image.open(source_path) as img:
        img = ImageOps.exif_transpose(img)  # respect camera/phone orientation metadata
        img = img.convert("RGB")
        img = ImageOps.fit(img, TARGET_SIZE, method=Image.LANCZOS)

        output_dir = Path(settings.STORAGE_ROOT) / output_subfolder
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "preprocessed.jpg"
        img.save(output_path, "JPEG", quality=95)

    return str(output_path.relative_to(Path(settings.STORAGE_ROOT))).replace("\\", "/")
