from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Enum, Float, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.persona import Persona
    from app.models.product_variant import ProductVariant
    from app.models.simulation import Simulation


class SentimentLabel(str, enum.Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class Feedback(Base, IDMixin, TimestampMixin):
    __tablename__ = "feedback"

    simulation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("simulations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_variants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    persona_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("personas.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    qualitative_text: Mapped[str] = mapped_column(Text, nullable=False)
    purchase_likelihood: Mapped[float] = mapped_column(Float, nullable=False)
    # sentiment_label/sentiment_score/engagement_score/risk_flags start null: persona
    # reactions (Step 21) populate qualitative_text/purchase_likelihood first, then
    # sentiment analysis (Step 23) and risk detection (Step 24) fill these in later
    # in the same pipeline run.
    sentiment_label: Mapped[Optional[SentimentLabel]] = mapped_column(
        Enum(SentimentLabel, name="sentiment_label"), nullable=True
    )
    sentiment_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    engagement_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_flags: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    consistency_variance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    iteration_number: Mapped[int] = mapped_column(Integer, nullable=False)

    simulation: Mapped["Simulation"] = relationship(back_populates="feedback_entries")
    variant: Mapped["ProductVariant"] = relationship(back_populates="feedback_entries")
    persona: Mapped["Persona"] = relationship(back_populates="feedback_entries")
