from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Enum, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.feedback import Feedback
    from app.models.simulation import Simulation


class PersonaSource(str, enum.Enum):
    SEEDED = "seeded"
    DYNAMIC = "dynamic"


class Persona(Base, IDMixin, TimestampMixin):
    __tablename__ = "personas"

    template_key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    age_min: Mapped[int] = mapped_column(Integer, nullable=False)
    age_max: Mapped[int] = mapped_column(Integer, nullable=False)
    income_segment: Mapped[str] = mapped_column(String, nullable=False)
    lifestyle: Mapped[str] = mapped_column(String, nullable=False)
    region: Mapped[str] = mapped_column(String, nullable=False)
    gender: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    behavior_traits: Mapped[dict] = mapped_column(JSONB, nullable=False)
    prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[PersonaSource] = mapped_column(
        Enum(PersonaSource, name="persona_source"), nullable=False, default=PersonaSource.SEEDED
    )

    simulations: Mapped[list["Simulation"]] = relationship(
        secondary="simulation_personas", back_populates="personas"
    )
    feedback_entries: Mapped[list["Feedback"]] = relationship(back_populates="persona")
