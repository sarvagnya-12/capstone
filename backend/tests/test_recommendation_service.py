"""Step 29: ranking/PMF scoring and recommendation persistence."""

import pytest

from app.models.product_variant import ProductVariant
from app.models.recommendation import Recommendation
from app.services import recommendation_service
from tests.conftest import make_feedback, make_persona, make_simulation_with_variants


def test_build_recommendation_raises_when_no_feedback_exists(db_session):
    simulation, variants = make_simulation_with_variants(db_session, n_variants=1)

    with pytest.raises(recommendation_service.NoFeedbackError):
        recommendation_service.build_recommendation(db_session, simulation.id)


def test_build_recommendation_scoped_to_final_iteration_only(db_session):
    """The plan's own explicit requirement: earlier rounds were superseded
    by the optimization loop, so only the final round's variants should
    ever be eligible for the recommendation -- not every variant generated
    across the whole simulation."""
    simulation, round_0_variants = make_simulation_with_variants(db_session, n_variants=2)
    persona = make_persona(db_session)
    for v in round_0_variants:
        make_feedback(db_session, simulation, v, persona, iteration_number=0, purchase_likelihood=0.9)

    round_1_variant = ProductVariant(
        product_id=round_0_variants[0].product_id, simulation_id=simulation.id,
        image_path="round1.jpg", attributes={}, generation_method="gan_latent_variation",
    )
    db_session.add(round_1_variant)
    db_session.flush()
    make_feedback(db_session, simulation, round_1_variant, persona, iteration_number=1, purchase_likelihood=0.5)

    recommendation = recommendation_service.build_recommendation(db_session, simulation.id)

    ranked_ids = {entry["variant_id"] for entry in recommendation.ranking}
    assert ranked_ids == {str(round_1_variant.id)}  # NOT round 0's 2 variants
    assert recommendation.recommended_variant_id == round_1_variant.id


def test_build_recommendation_normalizes_distinct_scores_to_0_100_range(db_session):
    simulation, variants = make_simulation_with_variants(db_session, n_variants=2)
    persona = make_persona(db_session)
    make_feedback(db_session, simulation, variants[0], persona, purchase_likelihood=0.9, sentiment_score=0.9)
    make_feedback(db_session, simulation, variants[1], persona, purchase_likelihood=0.1, sentiment_score=-0.9)

    recommendation = recommendation_service.build_recommendation(db_session, simulation.id)

    scores = sorted(entry["pmf_score"] for entry in recommendation.ranking)
    assert scores == [0.0, 100.0]
    assert recommendation.recommended_variant_id == variants[0].id


def test_build_recommendation_midpoint_fallback_when_all_scores_tied(db_session):
    simulation, variants = make_simulation_with_variants(db_session, n_variants=2)
    persona = make_persona(db_session)
    for v in variants:
        make_feedback(db_session, simulation, v, persona, purchase_likelihood=0.5, sentiment_score=0.0)

    recommendation = recommendation_service.build_recommendation(db_session, simulation.id)

    assert all(entry["pmf_score"] == 50.0 for entry in recommendation.ranking)


def test_build_recommendation_persists_one_row(db_session):
    simulation, variants = make_simulation_with_variants(db_session, n_variants=1)
    persona = make_persona(db_session)
    make_feedback(db_session, simulation, variants[0], persona, purchase_likelihood=0.9)

    recommendation_service.build_recommendation(db_session, simulation.id)

    rows = db_session.query(Recommendation).filter(Recommendation.simulation_id == simulation.id).all()
    assert len(rows) == 1
