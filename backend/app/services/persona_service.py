"""Implements FR#5 (PRD Sec9): persona-reaction simulation. For each
(persona, variant) pair in a simulation, builds the prompt (Step 20), calls
the LLM provider, and records a Feedback row. sentiment_label/sentiment_score/
engagement_score/risk_flags start null -- populated later by Phases 8-9
(sentiment analysis, risk detection), kept separate per the certified
architecture's own layering (LLM Persona Layer is distinct from downstream
analysis).
"""

import logging
import random
import re
import uuid

from sqlalchemy.orm import Session

from app.ml.llm.prompt_templates import (
    PersonaReactionParseError,
    build_persona_reaction_prompt,
    parse_persona_reaction,
)
from app.ml.llm.provider import LLMConfigurationError, get_llm_provider
from app.models.feedback import Feedback
from app.models.persona import Persona
from app.models.product_variant import ProductVariant
from app.models.simulation import Simulation

logger = logging.getLogger(__name__)

LLM_ERROR_PREFIX = "[LLM_ERROR]"

# Crude keyword-based polarity heuristic used ONLY as a lightweight proxy for
# check_consistency() below -- NOT real sentiment analysis (that's Step 23's
# job, using an actual NLP model). Good enough to notice "this rerun reads
# very differently," not a rigorous signal.
_POSITIVE_WORDS = {
    "love", "great", "amazing", "excellent", "good", "like", "want", "excited",
    "impressed", "nice", "solid", "worth", "appealing",
}
_NEGATIVE_WORDS = {
    "hate", "bad", "poor", "dislike", "disappointing", "overpriced", "unimpressed",
    "skip", "pass", "expensive", "cheap", "unconvinced", "meh",
}


def _crude_sentiment_proxy(text: str) -> float:
    words = re.findall(r"[a-z']+", text.lower())
    positive = sum(1 for w in words if w in _POSITIVE_WORDS)
    negative = sum(1 for w in words if w in _NEGATIVE_WORDS)
    total = positive + negative
    return 0.0 if total == 0 else (positive - negative) / total


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


def check_consistency(db: Session, simulation_id: uuid.UUID, sample_rate: float = 0.25) -> None:
    """Re-runs a sample of this simulation's persona reactions and records
    how much the result drifts from the original, as a lightweight
    reliability signal -- not a rigorous statistical framework, same category
    of documented limitation as Step 18's small-sample FID. Repeating every
    pair would double LLM cost/latency for marginal signal, so only a sample
    is re-run; unsampled rows are left with consistency_variance = NULL."""
    simulation = db.get(Simulation, simulation_id)
    if simulation is None:
        raise SimulationNotFoundError(simulation_id)

    all_feedback = db.query(Feedback).filter(Feedback.simulation_id == simulation_id).all()
    sample_size = min(len(all_feedback), max(1, round(len(all_feedback) * sample_rate))) if all_feedback else 0
    sampled = random.sample(all_feedback, sample_size)

    try:
        provider = get_llm_provider()
    except LLMConfigurationError:
        # Can't measure real consistency without a working provider -- leave
        # consistency_variance NULL rather than fabricate a number.
        logger.warning("check_consistency: no LLM provider configured, skipping re-check for simulation=%s", simulation_id)
        return

    variant_by_id = {v.id: v for v in db.query(ProductVariant).filter(ProductVariant.simulation_id == simulation_id)}
    persona_by_id = {p.id: p for p in db.query(Persona).filter(Persona.id.in_({f.persona_id for f in sampled}))}

    for feedback in sampled:
        persona = persona_by_id[feedback.persona_id]
        variant = variant_by_id[feedback.variant_id]

        prompt = build_persona_reaction_prompt(
            persona_prompt_template=persona.prompt_template,
            variant_attributes=variant.attributes,
            pricing_strategy=simulation.pricing_strategy,
            target_demographic=simulation.target_demographic,
            promotional_messaging=simulation.promotional_messaging,
        )

        try:
            raw_completion = provider.complete(prompt)
            parsed = parse_persona_reaction(raw_completion)
        except (PersonaReactionParseError, Exception) as e:
            logger.warning("Consistency re-check failed for feedback=%s: %s", feedback.id, e)
            continue

        likelihood_delta = abs(parsed["purchase_likelihood"] - feedback.purchase_likelihood)
        sentiment_delta = abs(
            _crude_sentiment_proxy(parsed["reaction_text"]) - _crude_sentiment_proxy(feedback.qualitative_text)
        )
        feedback.consistency_variance = (likelihood_delta + sentiment_delta) / 2

    db.commit()
