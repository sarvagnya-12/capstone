"""FR#4 "Run Simulation" (Fig 6.5) and scenario configuration (FR#3, Step 27)."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.persona import Persona
from app.models.recommendation import Recommendation
from app.models.simulation import Simulation
from app.models.user import User, UserRole
from app.schemas.recommendation import RecommendationResponse
from app.schemas.simulation import SimulationCreateRequest, SimulationResponse
from app.services import simulation_orchestrator
from app.services.persona_service import select_representative_personas
from app.services.product_service import ProductNotFoundError, get_product

router = APIRouter(prefix="/simulations", tags=["simulations"])


def _get_owned_simulation(db: Session, current_user: User, simulation_id: uuid.UUID) -> Simulation:
    simulation = db.get(Simulation, simulation_id)
    # Non-owners get 404, not 403 -- same ownership-scoping pattern as
    # product_service.get_product() (Step 11): avoids leaking existence of
    # another user's resources.
    if simulation is None or (current_user.role != UserRole.ADMIN and simulation.user_id != current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")
    return simulation


@router.post("", response_model=SimulationResponse, status_code=status.HTTP_202_ACCEPTED)
def create_simulation(
    payload: SimulationCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SimulationResponse:
    try:
        product = get_product(db, current_user, payload.product_id)
    except ProductNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    if payload.persona_ids:
        personas = db.query(Persona).filter(Persona.id.in_(payload.persona_ids)).all()
        if len(personas) != len(payload.persona_ids):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="One or more persona_ids not found"
            )
    else:
        personas = select_representative_personas(db)

    simulation = Simulation(
        product_id=product.id,
        user_id=current_user.id,
        pricing_strategy={"tiers": [tier.model_dump() for tier in payload.pricing_strategy]},
        target_demographic=payload.target_demographic.model_dump(exclude_none=True),
        promotional_messaging=payload.promotional_messaging,
        max_iterations=payload.max_iterations or 3,
    )
    db.add(simulation)
    db.commit()
    db.refresh(simulation)

    simulation.personas = personas
    db.commit()
    db.refresh(simulation)

    background_tasks.add_task(simulation_orchestrator.run, simulation.id, payload.variant_count)

    return simulation


@router.get("/{simulation_id}/status", response_model=SimulationResponse)
def get_simulation_status(
    simulation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SimulationResponse:
    return _get_owned_simulation(db, current_user, simulation_id)


@router.get("/{simulation_id}/recommendation", response_model=RecommendationResponse)
def get_simulation_recommendation(
    simulation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecommendationResponse:
    _get_owned_simulation(db, current_user, simulation_id)  # ownership check; 404s before revealing anything
    recommendation = db.query(Recommendation).filter(Recommendation.simulation_id == simulation_id).one_or_none()
    if recommendation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No recommendation yet for this simulation (it may still be running, or may have failed)",
        )
    return recommendation
