"""The integration point of the entire backend (Step 28): wires
Generate -> Simulate -> Evaluate -> Optimize -> (repeat) -> Recommend into
one orchestrated flow behind a single API call, satisfying FR#4's "Run
Simulation" use case (Fig 6.5) and the full Activity Diagram (Fig 6.4).

Runs as a FastAPI BackgroundTasks job (Decision #1: no Celery/Redis in the
MVP) -- POST /simulations returns immediately with a pollable id while this
runs in-process in the background. Treat changes here as high-risk: this is
the one place every prior phase's service is called together.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.simulation import Simulation, SimulationStatus
from app.services import gan_service, persona_service, recommendation_service, risk_service, sentiment_service
from app.services import optimization_service

logger = logging.getLogger(__name__)

DEFAULT_VARIANT_COUNT = 4


def run(simulation_id: uuid.UUID, variant_count: int = DEFAULT_VARIANT_COUNT) -> None:
    """Entry point for the FastAPI BackgroundTasks job. Owns its own DB
    session since it runs outside the normal request-scoped get_db()
    dependency lifecycle."""
    db = SessionLocal()
    try:
        _run_pipeline(db, simulation_id, variant_count)
    except Exception:
        logger.exception("Simulation %s failed", simulation_id)
        # Never leave a simulation silently stuck in a non-terminal status --
        # this except block is the one place that guarantees a terminal
        # state even when something above raises unexpectedly.
        simulation = db.get(Simulation, simulation_id)
        if simulation is not None:
            simulation.status = SimulationStatus.FAILED
            db.commit()
    finally:
        db.close()


def _run_pipeline(db: Session, simulation_id: uuid.UUID, variant_count: int) -> None:
    simulation = db.get(Simulation, simulation_id)
    if simulation is None:
        raise ValueError(f"Simulation {simulation_id} not found")

    attribute_hints: dict | None = None

    while True:
        iteration_label = simulation.iteration_count

        # 1. Generate
        simulation.status = SimulationStatus.GENERATING
        db.commit()
        round_variants = gan_service.generate_variants_for_simulation(
            db, simulation.id, variant_count, attribute_hints=attribute_hints
        )

        # 2. Simulate
        simulation.status = SimulationStatus.SIMULATING
        db.commit()
        # variant_ids scopes this call to THIS round's freshly-generated
        # variants only -- without it, every subsequent round would
        # re-simulate every earlier round's variants too (a real bug this
        # step's own end-to-end test caught: see persona_service's docstring).
        persona_service.simulate_persona_reactions(
            db, simulation.id, iteration_number=iteration_label, variant_ids=[v.id for v in round_variants]
        )
        persona_service.check_consistency(db, simulation.id)

        # 3. Evaluate
        simulation.status = SimulationStatus.EVALUATING
        db.commit()
        sentiment_service.classify_feedback(db, simulation.id)
        risk_service.detect_risks(db, simulation.id)

        # 4. Optimize / decide whether to continue
        simulation.status = SimulationStatus.OPTIMIZING
        db.commit()
        attribute_hints = optimization_service.propose_next_attributes(db, simulation.id)
        if not optimization_service.should_continue(db, simulation):
            break

    # 5. Recommend
    recommendation_service.build_recommendation(db, simulation.id)

    # 6. Complete
    simulation.status = SimulationStatus.COMPLETED
    simulation.completed_at = datetime.now(timezone.utc)
    db.commit()
