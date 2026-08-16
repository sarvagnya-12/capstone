from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.product_variant import ProductVariant
    from app.models.simulation import Simulation


class Recommendation(Base, IDMixin, TimestampMixin):
    __tablename__ = "recommendations"

    simulation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("simulations.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    recommended_variant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_variants.id", ondelete="RESTRICT"), nullable=False
    )
    pmf_score: Mapped[float] = mapped_column(Float, nullable=False)
    ranking: Mapped[dict] = mapped_column(JSONB, nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)

    simulation: Mapped["Simulation"] = relationship(back_populates="recommendation")
    recommended_variant: Mapped["ProductVariant"] = relationship()
