"""Implements FR#8 (PRD Sec9) per Decision #3: heuristic/threshold weighting,
NOT reinforcement learning or Bayesian/genetic search. Combines each
variant's sentiment, purchase-likelihood, engagement, and risk signals into
one explainable score, then proposes a narrowed attribute neighborhood for
the next generation round based on the top scorer -- the "latent-space
nudging + scenario weighting" mechanism named in the Abstract, implemented
as a concrete, deterministic function rather than an opaque model.
"""

import uuid
from collections import defaultdict
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.feedback import Feedback
from app.models.product_variant import ProductVariant
from app.models.simulation import Simulation

# Minimum score improvement between rounds to justify another iteration.
# Below this, the loop is judged to have plateaued (Decision #8 / Open
# Decision #6 -- no stopping rule was documented anywhere in the source
# material; this is the concrete rule this project adopts).
PLATEAU_THRESHOLD = 0.02

# Weights are documented defaults, not tuned against any labeled outcome data
# (none exists -- this is a simulated, not real-world-calibrated, signal).
SENTIMENT_WEIGHT = 0.3
PURCHASE_LIKELIHOOD_WEIGHT = 0.4
ENGAGEMENT_WEIGHT = 0.1
RISK_PENALTY_PER_FLAG = 0.3

# Reaction-text length (chars) treated as "fully engaged" for the engagement
# proxy below -- longer than this doesn't add further engagement score.
_ENGAGEMENT_LENGTH_CAP = 200

# Narrower than inference.py's default 0.4 -- once there's a known good
# neighborhood to nudge toward, the next round should converge, not keep
# exploring as broadly as the first (undirected) round.
_NUDGED_PERTURBATION_RADIUS = 0.15


def _engagement_proxy(text: str) -> float:
    """Crude proxy for "how much the persona had to say" -- reaction length
    normalized to [0, 1], per this step's own plan text suggesting feedback
    length/specificity as a stand-in absent an explicit engagement field."""
    return min(len(text) / _ENGAGEMENT_LENGTH_CAP, 1.0)


def score_variants(
    db: Session, simulation_id: uuid.UUID, iteration_number: Optional[int] = None
) -> dict[uuid.UUID, float]:
    """Weighted sum of mean sentiment_score, mean purchase_likelihood, and
    mean engagement proxy, minus a flat penalty per distinct risk rule
    triggered (Step 24). Deterministic and fully explainable from its
    inputs -- no randomness, no opaque model.

    iteration_number (added Step 28): scopes scoring to a single round when
    given (e.g. Step 29's build_recommendation() only wants the *final*
    round's variants ranked, not every historical round mixed together);
    omitted (None), scores every variant across all rounds, which is what
    Step 26's should_continue()/_best_score_by_iteration() need to compare
    across rounds."""
    stmt = select(Feedback).where(Feedback.simulation_id == simulation_id)
    if iteration_number is not None:
        stmt = stmt.where(Feedback.iteration_number == iteration_number)
    feedback_rows = list(db.execute(stmt).scalars().all())

    by_variant: dict[uuid.UUID, list[Feedback]] = defaultdict(list)
    for feedback in feedback_rows:
        by_variant[feedback.variant_id].append(feedback)

    scores: dict[uuid.UUID, float] = {}
    for variant_id, rows in by_variant.items():
        sentiment_scores = [r.sentiment_score for r in rows if r.sentiment_score is not None]
        likelihoods = [r.purchase_likelihood for r in rows if r.purchase_likelihood is not None]
        engagements = [_engagement_proxy(r.qualitative_text) for r in rows]

        mean_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.0
        mean_likelihood = sum(likelihoods) / len(likelihoods) if likelihoods else 0.0
        mean_engagement = sum(engagements) / len(engagements) if engagements else 0.0

        risk_rule_count = len(rows[0].risk_flags) if rows and rows[0].risk_flags else 0

        scores[variant_id] = (
            SENTIMENT_WEIGHT * mean_sentiment
            + PURCHASE_LIKELIHOOD_WEIGHT * mean_likelihood
            + ENGAGEMENT_WEIGHT * mean_engagement
            - RISK_PENALTY_PER_FLAG * risk_rule_count
        )

    return scores


def propose_next_attributes(db: Session, simulation_id: uuid.UUID) -> Optional[dict]:
    """Looks at the top-scoring variant's attributes JSON (Step 16's schema)
    and returns an attribute_hints dict that app.ml.gan.inference.
    generate_variants() can consume directly to narrow the next round's
    search toward that neighborhood. Returns None if there's nothing to
    score yet (e.g. no feedback exists for this simulation)."""
    scores = score_variants(db, simulation_id)
    if not scores:
        return None

    top_variant_id = max(scores, key=lambda vid: scores[vid])
    top_variant = db.get(ProductVariant, top_variant_id)
    if top_variant is None:
        return None

    attrs = top_variant.attributes
    return {
        "anchor_seed": attrs.get("anchor_seed"),
        "perturbation_radius": _NUDGED_PERTURBATION_RADIUS,
        "hue_shift_center_degrees": attrs.get("color_hue_shift_degrees"),
    }


def _best_score_by_iteration(db: Session, simulation_id: uuid.UUID) -> dict[int, float]:
    """Groups score_variants()'s per-variant scores by the iteration each
    variant was generated in -- looked up via its Feedback rows'
    iteration_number, which is uniform per variant since a variant is only
    ever scored within the one round it was generated in (Step 16 creates
    fresh ProductVariant rows every round). Returns the best score per
    iteration seen so far."""
    scores = score_variants(db, simulation_id)
    if not scores:
        return {}

    variant_iteration = dict(
        db.execute(
            select(Feedback.variant_id, Feedback.iteration_number)
            .where(Feedback.simulation_id == simulation_id)
            .distinct()
        ).all()
    )

    best_by_iteration: dict[int, float] = {}
    for variant_id, score in scores.items():
        iteration = variant_iteration.get(variant_id)
        if iteration is None:
            continue
        best_by_iteration[iteration] = max(best_by_iteration.get(iteration, float("-inf")), score)

    return best_by_iteration


def should_continue(db: Session, simulation: Simulation) -> bool:
    """Implements the Fig 6.4 "More Iterations?" decision (Decision #8):
    call once after each round (labeled iteration_number = the
    pre-call simulation.iteration_count) finishes. Returns False (stop) once
    that many rounds have now completed >= max_iterations, OR if the best
    score improved by less than PLATEAU_THRESHOLD versus the previous round.
    Otherwise returns True. Always updates simulation.iteration_count to the
    number of completed rounds before returning. Called by the orchestrator
    (Step 28) -- pure decision logic, kept testable in isolation from the
    orchestration plumbing around it.

    Counting note: iteration_count is the number of rounds *completed so
    far*, and rounds are labeled 0, 1, 2, ... -- so the round that just ran
    is round `simulation.iteration_count` (pre-update), and after it,
    completed_rounds = iteration_count + 1. Checking
    `iteration_count >= max_iterations` *before* accounting for the round
    that just finished is an off-by-one: it would let max_iterations=1 run a
    second round before stopping. Comparing completed_rounds instead is what
    makes "max_iterations=1 stops after exactly one round" (this step's own
    required test case) actually hold.
    """
    current = simulation.iteration_count  # the round that just finished
    completed_rounds = current + 1

    if completed_rounds >= simulation.max_iterations:
        simulation.iteration_count = completed_rounds
        db.commit()
        return False

    best_by_iteration = _best_score_by_iteration(db, simulation.id)
    if current in best_by_iteration and (current - 1) in best_by_iteration:
        improvement = best_by_iteration[current] - best_by_iteration[current - 1]
        if improvement < PLATEAU_THRESHOLD:
            simulation.iteration_count = completed_rounds
            db.commit()
            return False

    simulation.iteration_count = completed_rounds
    db.commit()
    return True
