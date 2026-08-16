from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.feedback import Feedback
    from app.models.product import Product
    from app.models.simulation import Simulation


class ProductVariant(Base, IDMixin, TimestampMixin):
    """Necessary elaboration beyond the certified class diagram (PRD Fig 6.3): Feedback
    must reference a specific generated variant, not just the parent Product. The
    certified diagram implies this via "GAN generates synthetic variations" (FR#4)
    without naming the entity explicitly.
    """

    __tablename__ = "product_variants"

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    simulation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("simulations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    image_path: Mapped[str] = mapped_column(String, nullable=False)
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False)
    generation_method: Mapped[str] = mapped_column(String, nullable=False)
    fid_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    product: Mapped["Product"] = relationship(back_populates="variants")
    simulation: Mapped["Simulation"] = relationship(back_populates="variants")
    feedback_entries: Mapped[list["Feedback"]] = relationship(back_populates="variant")
