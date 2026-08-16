"""FR#9 (PRD Sec9)'s backend half (Step 30): read-only aggregation endpoint
the frontend dashboard (Phase 14) will consume directly -- sentiment charts,
PMF score, variant ranking, and launch-risk indicators (PRD Sec25) in one
composed payload, so the frontend doesn't need to call and stitch together
several endpoints itself.
"""

import uuid
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.feedback import Feedback, SentimentLabel
from app.models.product_variant import ProductVariant
from app.models.recommendation import Recommendation
from app.models.simulation import Simulation
from app.models.user import User, UserRole
from app.schemas.dashboard import SentimentBreakdown, SimulationAnalyticsResponse, VariantAnalytics
from app.services.optimization_service import engagement_proxy

router = APIRouter(prefix="/simulations", tags=["dashboard"])


def _get_owned_simulation(db: Session, current_user: User, simulation_id: uuid.UUID) -> Simulation:
    simulation = db.get(Simulation, simulation_id)
    # Same ownership-scoping pattern as simulations.py: non-owners get 404,
    # not 403, to avoid leaking whether the resource exists at all.
    if simulation is None or (current_user.role != UserRole.ADMIN and simulation.user_id != current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")
    return simulation


@router.get("/{simulation_id}/analytics", response_model=SimulationAnalyticsResponse)
def get_simulation_analytics(
    simulation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SimulationAnalyticsResponse:
    simulation = _get_owned_simulation(db, current_user, simulation_id)

    # PMF/ranking is explicitly sourced from Recommendation.ranking (this
    # step's own plan text) -- which only exists once the simulation reaches
    # `completed` (Step 28's orchestrator builds it as its second-to-last
    # action). Rather than returning a payload with ranking present but
    # sentiment/risk computed over a different, inconsistent set of variants
    # for a still-running simulation, this endpoint requires the same
    # "not ready yet" precondition Step 29's recommendation endpoint already
    # established, and scopes every section of the response to exactly the
    # variant set recorded in that ranking.
    recommendation = db.query(Recommendation).filter(Recommendation.simulation_id == simulation_id).one_or_none()
    if recommendation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No analytics yet for this simulation (it may still be running, or may have failed)",
        )

    final_iteration = db.execute(
        select(func.max(Feedback.iteration_number)).where(Feedback.simulation_id == simulation_id)
    ).scalar()

    variant_ids = [uuid.UUID(entry["variant_id"]) for entry in recommendation.ranking]
    pmf_by_variant = {uuid.UUID(entry["variant_id"]): entry["pmf_score"] for entry in recommendation.ranking}

    feedback_rows = list(
        db.execute(
            select(Feedback).where(
                Feedback.simulation_id == simulation_id,
                Feedback.variant_id.in_(variant_ids),
            )
        )
        .scalars()
        .all()
    )
    by_variant: dict[uuid.UUID, list[Feedback]] = defaultdict(list)
    for row in feedback_rows:
        by_variant[row.variant_id].append(row)

    variants_out: list[VariantAnalytics] = []
    for rank, variant_id in enumerate(variant_ids, start=1):
        rows = by_variant.get(variant_id, [])

        sentiment = SentimentBreakdown(
            positive=sum(1 for r in rows if r.sentiment_label == SentimentLabel.POSITIVE),
            negative=sum(1 for r in rows if r.sentiment_label == SentimentLabel.NEGATIVE),
            neutral=sum(1 for r in rows if r.sentiment_label == SentimentLabel.NEUTRAL),
            unclassified=sum(1 for r in rows if r.sentiment_label is None),
        )

        likelihoods = [r.purchase_likelihood for r in rows if r.purchase_likelihood is not None]
        avg_purchase_likelihood = sum(likelihoods) / len(likelihoods) if likelihoods else None

        engagements = [engagement_proxy(r.qualitative_text) for r in rows]
        avg_engagement_score = sum(engagements) / len(engagements) if engagements else None

        # risk_flags is denormalized across every Feedback row for a variant
        # (risk_service.py writes the same list to each row) -- any one
        # non-null instance is representative.
        risk_flags = next((r.risk_flags for r in rows if r.risk_flags), [])

        variant = db.get(ProductVariant, variant_id)

        variants_out.append(
            VariantAnalytics(
                variant_id=variant_id,
                rank=rank,
                pmf_score=pmf_by_variant[variant_id],
                is_recommended=(variant_id == recommendation.recommended_variant_id),
                sentiment=sentiment,
                avg_purchase_likelihood=avg_purchase_likelihood,
                avg_engagement_score=avg_engagement_score,
                risk_flags=risk_flags,
                fid_score=variant.fid_score if variant is not None else None,
            )
        )

    return SimulationAnalyticsResponse(
        simulation_id=simulation.id,
        status=simulation.status,
        final_iteration=final_iteration if final_iteration is not None else 0,
        recommended_variant_id=recommendation.recommended_variant_id,
        pmf_score=recommendation.pmf_score,
        summary_text=recommendation.summary_text,
        scenario={
            "pricing_strategy": simulation.pricing_strategy,
            "target_demographic": simulation.target_demographic,
            "promotional_messaging": simulation.promotional_messaging,
            "max_iterations": simulation.max_iterations,
        },
        variants=variants_out,
    )
