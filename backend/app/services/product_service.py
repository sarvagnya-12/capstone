import uuid
from pathlib import Path
from typing import Optional

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.user import User, UserRole
from app.services import storage_service

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10MB


class InvalidImageUploadError(Exception):
    pass


class ProductNotFoundError(Exception):
    pass


def _validate_image(file: UploadFile) -> None:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise InvalidImageUploadError(f"Unsupported content type: {file.content_type}")

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise InvalidImageUploadError(f"Unsupported file extension: {suffix}")

    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    if size > MAX_UPLOAD_SIZE_BYTES:
        raise InvalidImageUploadError(f"File too large: {size} bytes (max {MAX_UPLOAD_SIZE_BYTES})")
    if size == 0:
        raise InvalidImageUploadError("Uploaded file is empty")


def create_product(
    db: Session,
    user: User,
    name: str,
    description: str,
    category: str,
    image: UploadFile,
    brand: Optional[str] = None,
    branding_details: Optional[str] = None,
) -> Product:
    _validate_image(image)

    product_id = uuid.uuid4()
    relative_path = storage_service.save_upload(image, subfolder=f"products/{product_id}")

    product = Product(
        id=product_id,
        user_id=user.id,
        name=name,
        description=description,
        brand=brand,
        category=category,
        branding_details=branding_details,
        original_image_path=relative_path,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def list_products(db: Session, user: User) -> list[Product]:
    stmt = select(Product)
    if user.role != UserRole.ADMIN:
        stmt = stmt.where(Product.user_id == user.id)
    return list(db.execute(stmt).scalars().all())


def get_product(db: Session, user: User, product_id: uuid.UUID) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise ProductNotFoundError(product_id)
    # Non-owners get "not found", not "forbidden" -- avoids leaking existence of
    # another user's resources.
    if user.role != UserRole.ADMIN and product.user_id != user.id:
        raise ProductNotFoundError(product_id)
    return product
