"""FR#10 (PRD Sec9): ranking/scoring for final recommendation, using the
aggregate-persona-metric approach for "product-market fit" (Decision #9) --
explicitly NOT a market-dynamics/economic-model output.

build_recommendation()'s core logic was necessarily built together with
Step 28's orchestrator (which calls it as its final step to ever reach
"completed" status) rather than strictly "after" it -- Step 29's own plan
text acknowledges this coupling ("called from within the orchestrator's
final step ... described as its own step since it satisfies a distinct
FR"). This file is Step 29's core deliverable, pulled forward; the GET
retrieval endpoint (Step 29's other deliverable) is added separately when
that step is formally done.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.feedback import Feedback
from app.models.product_variant import ProductVariant
from app.models.recommendation import Recommendation
from app.services.optimization_service import score_variants

# score_variants() isn't bounded to a fixed range; normalize its spread onto
# a 0-100 "PMF score" for a human-readable, comparable number.
PMF_SCALE_MIN = 0.0
PMF_SCALE_MAX = 100.0


class NoFeedbackError(Exception):
    pass


def _normalize_to_pmf_scale(raw_scores: dict[uuid.UUID, float]) -> dict[uuid.UUID, float]:
    values = list(raw_scores.values())
    lo, hi = min(values), max(values)
    if hi == lo:
        # All variants scored identically -- put them all at the midpoint
        # rather than dividing by zero.
        midpoint = (PMF_SCALE_MIN + PMF_SCALE_MAX) / 2
        return {vid: midpoint for vid in raw_scores}
    return {
        vid: PMF_SCALE_MIN + (score - lo) / (hi - lo) * (PMF_SCALE_MAX - PMF_SCALE_MIN)
        for vid, score in raw_scores.items()
    }


def build_recommendation(db: Session, simulation_id: uuid.UUID) -> Recommendation:
    # Only the FINAL iteration's variants are eligible, per this step's own
    # plan text ("takes the final iteration's variant scores") -- earlier
    # rounds were deliberately superseded by the optimization loop's
    # nudging (Step 25/26), not meant to still compete in the final ranking.
    final_iteration = db.execute(
        select(func.max(Feedback.iteration_number)).where(Feedback.simulation_id == simulation_id)
    ).scalar()
    if final_iteration is None:
        raise NoFeedbackError(f"No feedback exists yet for simulation {simulation_id}")

    raw_scores = score_variants(db, simulation_id, iteration_number=final_iteration)
    if not raw_scores:
        raise NoFeedbackError(f"No scoreable variants for simulation {simulation_id} at iteration {final_iteration}")

    pmf_scores = _normalize_to_pmf_scale(raw_scores)
    ranked = sorted(pmf_scores.items(), key=lambda item: item[1], reverse=True)
    ranking = [{"variant_id": str(variant_id), "pmf_score": round(score, 1)} for variant_id, score in ranked]

    top_variant_id, top_pmf_score = ranked[0]
    top_variant = db.get(ProductVariant, top_variant_id)

    summary_text = (
        f"Variant {str(top_variant_id)[:8]} scored highest overall (PMF score {top_pmf_score:.1f}/100), "
        f"based on aggregate persona sentiment, purchase intent, and engagement across "
        f"{len(ranking)} generated variant(s) in the final iteration."
    )
    if top_variant is not None and top_variant.fid_score is not None:
        summary_text += f" Realism score (FID): {top_variant.fid_score:.1f}."

    recommendation = Recommendation(
        simulation_id=simulation_id,
        recommended_variant_id=top_variant_id,
        pmf_score=top_pmf_score,
        ranking=ranking,
        summary_text=summary_text,
    )
    db.add(recommendation)
    db.commit()
    db.refresh(recommendation)
    return recommendation
