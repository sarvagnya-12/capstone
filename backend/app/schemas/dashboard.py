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


class CustomerReactionOut(BaseModel):
    profile: str
    buying_intent: str
    likelihood_pct: int
    reaction: str
    comment: str


class OptionInsightOut(BaseModel):
    variant_id: uuid.UUID
    label: str
    colourway: str
    rank: int
    is_recommended: bool
    purchase_intent_pct: int
    interest_level: str
    likely_buyers: int
    undecided: int
    unlikely_buyers: int
    profiles: int
    liked: int
    neutral: int
    disliked: int
    reception: str
    appeals_most_to: list[str]
    least_interested: list[str]
    best_quote: Optional[CustomerReactionOut]
    worst_quote: Optional[CustomerReactionOut]
    concerns: list[str]
    themes: list[dict]
    reactions: list[CustomerReactionOut]


class SimulationInsightsOut(BaseModel):
    """Business-facing restatement of the results (app/services/insights_service.py):
    what the dashboard and reports show to a non-technical reader."""

    product_name: str
    product_brand: Optional[str]
    product_category: Optional[str]
    price_text: str
    audience_text: str
    messaging: Optional[str]
    profiles_tested: int
    options_tested: int
    rounds_run: int
    verdict: str
    bottom_line: str
    recommended_label: str
    options: list[OptionInsightOut]
    next_steps: list[str]
    disclaimer: str


class SimulationAnalyticsResponse(BaseModel):
    simulation_id: uuid.UUID
    status: SimulationStatus
    final_iteration: int
    recommended_variant_id: uuid.UUID
    pmf_score: float
    summary_text: str
    scenario: dict
    variants: list[VariantAnalytics]
    insights: SimulationInsightsOut
