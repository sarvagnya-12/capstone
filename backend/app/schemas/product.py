import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ProductResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str
    brand: Optional[str]
    category: str
    branding_details: Optional[str]
    original_image_path: str
    preprocessed_image_path: Optional[str]
    created_at: datetime
