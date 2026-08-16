"""Implements FR#5 (PRD Sec9): persona-reaction simulation. For each
(persona, variant) pair in a simulation, builds the prompt (Step 20), calls
the LLM provider, and records a Feedback row. sentiment_label/sentiment_score/
engagement_score/risk_flags start null -- populated later by Phases 8-9
(sentiment analysis, risk detection), kept separate per the certified
architecture's own layering (LLM Persona Layer is distinct from downstream
analysis).
"""

import logging
import uuid

from sqlalchemy.orm import Session

from app.ml.llm.prompt_templates import (
    PersonaReactionParseError,
    build_persona_reaction_prompt,
    parse_persona_reaction,
)
from app.ml.llm.provider import LLMConfigurationError, get_llm_provider
from app.models.feedback import Feedback
from app.models.product_variant import ProductVariant
from app.models.simulation import Simulation

logger = logging.getLogger(__name__)

LLM_ERROR_PREFIX = "[LLM_ERROR]"


class SimulationNotFoundError(Exception):
    pass


def simulate_persona_reactions(db: Session, simulation_id: uuid.UUID, iteration_number: int = 0) -> list[Feedback]:
    simulation = db.get(Simulation, simulation_id)
    if simulation is None:
        raise SimulationNotFoundError(simulation_id)

    variants = db.query(ProductVariant).filter(ProductVariant.simulation_id == simulation.id).all()
    personas = simulation.personas

    try:
        provider = get_llm_provider()
        provider_error: str | None = None
    except LLMConfigurationError as e:
        provider = None
        provider_error = str(e)

    feedback_rows = []
    for variant in variants:
        for persona in personas:
            prompt = build_persona_reaction_prompt(
                persona_prompt_template=persona.prompt_template,
                variant_attributes=variant.attributes,
                pricing_strategy=simulation.pricing_strategy,
                target_demographic=simulation.target_demographic,
                promotional_messaging=simulation.promotional_messaging,
            )

            if provider is None:
                # One bad/unconfigured provider must not abort the whole
                # simulation -- record a clearly-marked error row per pair
                # and keep going, per this step's own plan text.
                qualitative_text = f"{LLM_ERROR_PREFIX} {provider_error}"
                purchase_likelihood = 0.0
            else:
                try:
                    raw_completion = provider.complete(prompt)
                    parsed = parse_persona_reaction(raw_completion)
                    qualitative_text = parsed["reaction_text"]
                    purchase_likelihood = parsed["purchase_likelihood"]
                except (PersonaReactionParseError, Exception) as e:
                    logger.warning(
                        "Persona reaction failed for persona=%s variant=%s: %s", persona.id, variant.id, e
                    )
                    qualitative_text = f"{LLM_ERROR_PREFIX} {e}"
                    purchase_likelihood = 0.0

            feedback = Feedback(
                simulation_id=simulation.id,
                variant_id=variant.id,
                persona_id=persona.id,
                qualitative_text=qualitative_text,
                purchase_likelihood=purchase_likelihood,
                iteration_number=iteration_number,
            )
            db.add(feedback)
            feedback_rows.append(feedback)

    db.commit()
    for feedback in feedback_rows:
        db.refresh(feedback)
    return feedback_rows
