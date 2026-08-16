"""Request/response schemas for FR#3 (PRD Sec9): scenario configuration,
captured as part of simulation creation (Step 28) -- creating a simulation
*is* configuring its scenario, per this step's own plan text.
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.simulation import SimulationStatus


class PricingTier(BaseModel):
    tier_name: str = Field(min_length=1)
    price: float = Field(gt=0)


class TargetDemographic(BaseModel):
    # Same field names as the Persona model's own columns (age_min/age_max/
    # income_segment/region/lifestyle/gender), so scenario targeting and
    # persona attributes line up field-for-field for later matching/
    # filtering of which seeded personas are most relevant to this scenario.
    age_min: Optional[int] = Field(default=None, ge=0, le=120)
    age_max: Optional[int] = Field(default=None, ge=0, le=120)
    gender: Optional[str] = None
    income_segment: Optional[str] = None
    region: Optional[str] = None
    lifestyle: Optional[str] = None


class SimulationCreateRequest(BaseModel):
    product_id: uuid.UUID
    pricing_strategy: list[PricingTier] = Field(min_length=1)
    target_demographic: TargetDemographic
    promotional_messaging: Optional[str] = None
    # If omitted, Step 28's orchestrator defaults to a representative sample
    # from the persona library rather than requiring the caller to know
    # every persona id up front.
    persona_ids: Optional[list[uuid.UUID]] = None
    variant_count: int = Field(default=4, ge=1, le=20)
    max_iterations: Optional[int] = Field(default=None, ge=1, le=10)


class SimulationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    product_id: uuid.UUID
    user_id: uuid.UUID
    pricing_strategy: dict
    target_demographic: dict
    promotional_messaging: Optional[str]
    status: SimulationStatus
    iteration_count: int
    max_iterations: int
    created_at: datetime
    completed_at: Optional[datetime]
