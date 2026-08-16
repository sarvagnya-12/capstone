import uuid
from datetime import datetime

from pydantic import BaseModel


class RecommendationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    simulation_id: uuid.UUID
    recommended_variant_id: uuid.UUID
    pmf_score: float
    ranking: list
    summary_text: str
    created_at: datetime
