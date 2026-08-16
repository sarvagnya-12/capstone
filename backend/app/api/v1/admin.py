"""Admin actor's UI backing (Fig 6.3: Admin "manages users, monitors
simulations", Step 37). Read-only -- PRD Sec12 only names viewing as the
certified admin capability; no destructive admin action is specified, so
none is built beyond it.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_admin_user
from app.db.session import get_db
from app.models.simulation import Simulation
from app.models.user import User
from app.schemas.auth import UserResponse
from app.schemas.simulation import SimulationResponse

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserResponse])
def list_all_users(
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> list[User]:
    return db.query(User).order_by(User.email).all()


@router.get("/simulations", response_model=list[SimulationResponse])
def list_all_simulations(
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> list[Simulation]:
    return db.query(Simulation).order_by(Simulation.created_at.desc()).all()
