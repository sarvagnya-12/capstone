import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.product import ProductResponse
from app.services import storage_service
from app.services.product_service import (
    InvalidImageUploadError,
    ProductNotFoundError,
    create_product,
    get_product,
    list_products,
)

router = APIRouter(prefix="/products", tags=["products"])


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def upload_product(
    name: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    brand: Optional[str] = Form(None),
    branding_details: Optional[str] = Form(None),
    image: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProductResponse:
    try:
        product = create_product(
            db,
            current_user,
            name,
            description,
            category,
            image,
            brand=brand,
            branding_details=branding_details,
        )
    except InvalidImageUploadError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return product


@router.get("", response_model=list[ProductResponse])
def list_my_products(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProductResponse]:
    return list_products(db, current_user)


@router.get("/{product_id}", response_model=ProductResponse)
def get_product_by_id(
    product_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProductResponse:
    try:
        return get_product(db, current_user, product_id)
    except ProductNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")


@router.get("/{product_id}/image")
def get_product_image(
    product_id: uuid.UUID,
    kind: Literal["original", "preprocessed"] = "original",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Serves the uploaded/preprocessed product image (Step 34). Not a
    public static mount: every other resource in this app is
    ownership-scoped (404, not 403, for non-owners), and a blanket
    `StaticFiles` mount at a guessable path would let anyone with a leaked
    or enumerated UUID view another user's uploaded photos without
    authentication. Routing through get_product() keeps that same
    guarantee for images."""
    try:
        product = get_product(db, current_user, product_id)
    except ProductNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    relative_path = product.original_image_path if kind == "original" else product.preprocessed_image_path
    if relative_path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No {kind} image for this product")

    file_path = storage_service.get_path(relative_path)
    if not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image file missing on disk")

    return FileResponse(file_path)
