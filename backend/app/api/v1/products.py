import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.product import ProductResponse
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
