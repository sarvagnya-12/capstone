"""Response shapes for FR#9 (PRD Sec9)'s backend half (Step 30): dashboard
analytics. Read-only reshaping of data already produced by Phases 6-12 --
no new scoring/business logic is defined here, only aggregation for display.
"""

import uuid
from typing import Optional

from pydantic import BaseModel

from app.models.simulation import SimulationStatus


class SentimentBreakdown(BaseModel):
    positive: int
    negative: int
    neutral: int
    unclassified: int  # sentiment_label still null -- e.g. an [LLM_ERROR] row


class PersonaFeedbackEntry(BaseModel):
    persona_id: uuid.UUID
    persona_name: str
    qualitative_text: str
    purchase_likelihood: float
    sentiment_label: Optional[str]


class VariantAnalytics(BaseModel):
    variant_id: uuid.UUID
    rank: int
    pmf_score: float
    is_recommended: bool
    sentiment: SentimentBreakdown
    avg_purchase_likelihood: Optional[float]
    avg_engagement_score: Optional[float]
    risk_flags: list[dict]
    fid_score: Optional[float]
    # Added alongside the frontend dashboard (Step 36): the plan's own
    # "expandable per-persona feedback list" requirement needs the
    # qualitative "why" behind the scores, which the aggregate sentiment
    # counts above don't carry.
    feedback: list[PersonaFeedbackEntry]


class SimulationAnalyticsResponse(BaseModel):
    simulation_id: uuid.UUID
    status: SimulationStatus
    final_iteration: int
    recommended_variant_id: uuid.UUID
    pmf_score: float
    summary_text: str
    scenario: dict
    variants: list[VariantAnalytics]
