from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.simulation import Simulation


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class User(Base, IDMixin, TimestampMixin):
    __tablename__ = "users"

    org_name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), nullable=False, default=UserRole.USER
    )

    products: Mapped[list["Product"]] = relationship(back_populates="user")
    simulations: Mapped[list["Simulation"]] = relationship(back_populates="user")
