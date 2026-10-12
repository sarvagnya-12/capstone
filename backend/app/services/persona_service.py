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
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.ml.llm.prompt_templates import (
    PersonaReactionParseError,
    build_persona_reaction_prompt,
    describe_product,
    parse_persona_reaction,
)
from app.ml.llm.provider import LLMConfigurationError, get_llm_provider
from app.ml.retrieval.reviews import fetch_reference_reviews
from app.models.feedback import Feedback
from app.models.persona import Persona
from app.models.product_variant import ProductVariant
from app.models.simulation import Simulation
from app.services.storage_service import get_path

logger = logging.getLogger(__name__)


class _PromptContext:
    """Everything a persona prompt needs beyond the persona and variant
    themselves, computed once per simulation and shared by
    simulate_persona_reactions() and check_consistency(), so a consistency
    re-run sees exactly the inputs the original call saw."""

    def __init__(self, db: Session, simulation: Simulation) -> None:
        self._db = db
        self.simulation = simulation
        product = simulation.product
        self.product_description = describe_product(product.name, product.brand, product.category,
                                                     product.description)
        self._reviews_by_persona: dict = {}
        self._grounding_disabled_reason: Optional[str] = None

    def reference_reviews(self, persona: Persona) -> Optional[list[dict]]:
        """Real reviews for this persona, retrieved once per persona per
        simulation (the product is the same for every variant). A missing or
        broken index degrades to ungrounded prompts with one warning --
        grounding improves reactions, it is not worth failing a simulation over."""
        if not settings.REVIEW_GROUNDING_ENABLED or self._grounding_disabled_reason:
            return None
        if persona.id not in self._reviews_by_persona:
            try:
                self._reviews_by_persona[persona.id] = fetch_reference_reviews(
                    self._db, self.product_description, persona.prompt_template,
                    settings.REVIEW_GROUNDING_K, settings.REVIEW_INDEX_DIR,
                )
            except Exception as e:
                self._grounding_disabled_reason = str(e)
                logger.warning("Review grounding unavailable, continuing without it: %s", e)
                return None
        return self._reviews_by_persona[persona.id]

    def build(self, persona: Persona, variant: ProductVariant) -> tuple[str, Optional[list[bytes]]]:
        images = _variant_image(variant) if settings.LLM_VISION else None
        prompt = build_persona_reaction_prompt(
            persona_prompt_template=persona.prompt_template,
            variant_attributes=variant.attributes,
            pricing_strategy=self.simulation.pricing_strategy,
            target_demographic=self.simulation.target_demographic,
            promotional_messaging=self.simulation.promotional_messaging,
            product_description=self.product_description,
            has_image=bool(images),
            reference_reviews=self.reference_reviews(persona),
        )
        return prompt, images


def _variant_image(variant: ProductVariant) -> Optional[list[bytes]]:
    try:
        return [get_path(variant.image_path).read_bytes()]
    except OSError as e:
        # The persona can still react to the text description; say so in the
        # log rather than failing the pair.
        logger.warning("Variant image unreadable for variant=%s, sending text only: %s", variant.id, e)
        return None

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


DEFAULT_REPRESENTATIVE_PERSONA_COUNT = 5


class SimulationNotFoundError(Exception):
    pass


def select_representative_personas(db: Session, count: int = DEFAULT_REPRESENTATIVE_PERSONA_COUNT) -> list[Persona]:
    """Used by Step 28's simulation-creation endpoint when the caller doesn't
    specify persona_ids explicitly. Picks up to `count` personas spread
    across distinct lifestyle categories for diversity, not matched against
    the scenario's target_demographic -- demographic-aware selection is a
    reasonable future enhancement, not required by the plan text ("a
    representative sample from the library")."""
    all_personas = db.query(Persona).order_by(Persona.lifestyle, Persona.name).all()

    selected: list[Persona] = []
    seen_lifestyles: set = set()
    for persona in all_personas:
        if persona.lifestyle not in seen_lifestyles:
            selected.append(persona)
            seen_lifestyles.add(persona.lifestyle)
        if len(selected) >= count:
            break

    if len(selected) < count:
        remaining = [p for p in all_personas if p not in selected]
        selected.extend(remaining[: count - len(selected)])

    return selected


def simulate_persona_reactions(
    db: Session,
    simulation_id: uuid.UUID,
    iteration_number: int = 0,
    variant_ids: Optional[list[uuid.UUID]] = None,
) -> list[Feedback]:
    """variant_ids (added Step 28): scopes simulation to a specific set of
    variants -- critical for a multi-iteration simulation, where
    ProductVariant has no iteration column of its own and simply querying
    "all variants for this simulation" would re-simulate every earlier
    round's variants again on each subsequent round (a real bug caught by
    Step 28's own end-to-end test: round 2 produced 6 variants x 5 personas
    instead of the expected 3 x 5, because it silently included round 1's
    variants too). Omitted (None), preserves Step 21's original tested
    behavior of processing every variant in the simulation -- correct for a
    single-iteration call, not for the orchestrator's loop."""
    simulation = db.get(Simulation, simulation_id)
    if simulation is None:
        raise SimulationNotFoundError(simulation_id)

    variant_query = db.query(ProductVariant).filter(ProductVariant.simulation_id == simulation.id)
    if variant_ids is not None:
        variant_query = variant_query.filter(ProductVariant.id.in_(variant_ids))
    variants = variant_query.all()
    personas = simulation.personas

    try:
        provider = get_llm_provider()
        provider_error: str | None = None
    except LLMConfigurationError as e:
        provider = None
        provider_error = str(e)

    context = _PromptContext(db, simulation)
    feedback_rows = []
    for variant in variants:
        for persona in personas:
            prompt, images = context.build(persona, variant)

            if provider is None:
                # One bad/unconfigured provider must not abort the whole
                # simulation -- record a clearly-marked error row per pair
                # and keep going, per this step's own plan text.
                qualitative_text = f"{LLM_ERROR_PREFIX} {provider_error}"
                purchase_likelihood = 0.0
            else:
                try:
                    raw_completion = provider.complete(prompt, images=images)
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

    context = _PromptContext(db, simulation)
    for feedback in sampled:
        persona = persona_by_id[feedback.persona_id]
        variant = variant_by_id[feedback.variant_id]
        prompt, images = context.build(persona, variant)

        try:
            raw_completion = provider.complete(prompt, images=images)
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
