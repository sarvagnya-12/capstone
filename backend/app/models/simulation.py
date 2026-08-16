from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, Table, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.feedback import Feedback
    from app.models.persona import Persona
    from app.models.product import Product
    from app.models.product_variant import ProductVariant
    from app.models.recommendation import Recommendation
    from app.models.user import User


class SimulationStatus(str, enum.Enum):
    PENDING = "pending"
    GENERATING = "generating"
    SIMULATING = "simulating"
    EVALUATING = "evaluating"
    OPTIMIZING = "optimizing"
    COMPLETED = "completed"
    FAILED = "failed"


simulation_personas = Table(
    "simulation_personas",
    Base.metadata,
    Column("simulation_id", Uuid, ForeignKey("simulations.id", ondelete="CASCADE"), primary_key=True),
    Column("persona_id", Uuid, ForeignKey("personas.id", ondelete="RESTRICT"), primary_key=True),
)


class Simulation(Base, IDMixin, TimestampMixin):
    __tablename__ = "simulations"

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    pricing_strategy: Mapped[dict] = mapped_column(JSONB, nullable=False)
    target_demographic: Mapped[dict] = mapped_column(JSONB, nullable=False)
    promotional_messaging: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[SimulationStatus] = mapped_column(
        Enum(SimulationStatus, name="simulation_status"), nullable=False, default=SimulationStatus.PENDING
    )
    iteration_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_iterations: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    product: Mapped["Product"] = relationship(back_populates="simulations")
    user: Mapped["User"] = relationship(back_populates="simulations")
    variants: Mapped[list["ProductVariant"]] = relationship(
        back_populates="simulation", cascade="all, delete-orphan"
    )
    personas: Mapped[list["Persona"]] = relationship(
        secondary=simulation_personas, back_populates="simulations"
    )
    feedback_entries: Mapped[list["Feedback"]] = relationship(
        back_populates="simulation", cascade="all, delete-orphan"
    )
    recommendation: Mapped[Optional["Recommendation"]] = relationship(
        back_populates="simulation", cascade="all, delete-orphan"
    )
