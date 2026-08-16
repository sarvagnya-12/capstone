"""Step 25/26: heuristic scoring and iteration-loop stopping criteria.
Includes a regression test for the real off-by-one bug found by hand-tracing
this step's own required test case before writing any code: naively checking
iteration_count >= max_iterations *before* accounting for the round that
just finished would let max_iterations=1 run a second round."""

from app.services import optimization_service
from tests.conftest import make_feedback, make_persona, make_simulation_with_variants


def test_score_variants_weighted_formula(db_session):
    simulation, variants = make_simulation_with_variants(db_session, n_variants=2)
    persona = make_persona(db_session)
    make_feedback(
        db_session, simulation, variants[0], persona,
        purchase_likelihood=1.0, sentiment_score=1.0, qualitative_text="x" * 200,
    )
    make_feedback(
        db_session, simulation, variants[1], persona,
        purchase_likelihood=0.0, sentiment_score=-1.0, qualitative_text="short",
    )

    scores = optimization_service.score_variants(db_session, simulation.id)

    assert scores[variants[0].id] > scores[variants[1].id]


def test_score_variants_penalizes_risk_flags(db_session):
    simulation, variants = make_simulation_with_variants(db_session, n_variants=2)
    persona = make_persona(db_session)
    # Identical sentiment/purchase signal on both variants -- only variant 0
    # has a risk flag, so it alone should be penalized.
    make_feedback(
        db_session, simulation, variants[0], persona,
        purchase_likelihood=0.9, sentiment_score=0.9,
        risk_flags=[{"rule": "low_purchase_likelihood", "severity": "high", "detail": "x"}],
    )
    make_feedback(db_session, simulation, variants[1], persona, purchase_likelihood=0.9, sentiment_score=0.9)

    scores = optimization_service.score_variants(db_session, simulation.id)

    assert scores[variants[0].id] < scores[variants[1].id]
    assert scores[variants[1].id] - scores[variants[0].id] == optimization_service.RISK_PENALTY_PER_FLAG


def test_score_variants_scoped_to_iteration_number(db_session):
    simulation, variants = make_simulation_with_variants(db_session, n_variants=1)
    persona = make_persona(db_session)
    make_feedback(db_session, simulation, variants[0], persona, iteration_number=0, purchase_likelihood=0.9)
    make_feedback(db_session, simulation, variants[0], persona, iteration_number=1, purchase_likelihood=0.1)

    all_rounds = optimization_service.score_variants(db_session, simulation.id)
    round_0_only = optimization_service.score_variants(db_session, simulation.id, iteration_number=0)

    # all_rounds averages both feedback rows together; round_0_only sees only the high one.
    assert round_0_only[variants[0].id] > all_rounds[variants[0].id]


def test_should_continue_stops_after_exactly_one_round_when_max_iterations_is_one(db_session):
    """The exact required scenario from this step's own plan text -- the
    scenario whose hand-traced failure caught the off-by-one bug before any
    code was written."""
    simulation, variants = make_simulation_with_variants(db_session, n_variants=1, max_iterations=1)
    persona = make_persona(db_session)
    make_feedback(db_session, simulation, variants[0], persona, iteration_number=0, purchase_likelihood=0.5)
    db_session.flush()

    should_continue = optimization_service.should_continue(db_session, simulation)

    assert should_continue is False
    assert simulation.iteration_count == 1  # exactly one completed round, not two


def test_should_continue_true_when_under_max_and_improving(db_session):
    simulation, variants = make_simulation_with_variants(db_session, n_variants=1, max_iterations=5)
    persona = make_persona(db_session)
    make_feedback(db_session, simulation, variants[0], persona, iteration_number=0, purchase_likelihood=0.5)
    db_session.flush()

    should_continue = optimization_service.should_continue(db_session, simulation)

    assert should_continue is True
    assert simulation.iteration_count == 1


def test_should_continue_stops_on_plateau(db_session):
    from app.models.product_variant import ProductVariant

    # _best_score_by_iteration() assumes one variant belongs to exactly one
    # round (true in production -- Step 16 always creates a fresh
    # ProductVariant per round), so round 1 needs its own variant row here
    # too, not a second Feedback row reusing round 0's variant.
    simulation, round_0_variants = make_simulation_with_variants(db_session, n_variants=1, max_iterations=10)
    persona = make_persona(db_session)
    make_feedback(db_session, simulation, round_0_variants[0], persona, iteration_number=0, purchase_likelihood=0.50)
    simulation.iteration_count = 1
    db_session.flush()

    round_1_variant = ProductVariant(
        product_id=round_0_variants[0].product_id, simulation_id=simulation.id,
        image_path="round1.jpg", attributes={}, generation_method="gan_latent_variation",
    )
    db_session.add(round_1_variant)
    db_session.flush()
    # Round 1 scores almost identically to round 0 -- below PLATEAU_THRESHOLD.
    make_feedback(db_session, simulation, round_1_variant, persona, iteration_number=1, purchase_likelihood=0.501)
    db_session.flush()

    should_continue = optimization_service.should_continue(db_session, simulation)

    assert should_continue is False
    assert simulation.iteration_count == 2


def test_propose_next_attributes_targets_top_scorer(db_session):
    simulation, variants = make_simulation_with_variants(db_session, n_variants=2)
    variants[0].attributes = {"anchor_seed": 111, "color_hue_shift_degrees": 45}
    variants[1].attributes = {"anchor_seed": 222, "color_hue_shift_degrees": 90}
    db_session.flush()
    persona = make_persona(db_session)
    make_feedback(db_session, simulation, variants[0], persona, purchase_likelihood=0.9, sentiment_score=0.9)
    make_feedback(db_session, simulation, variants[1], persona, purchase_likelihood=0.1, sentiment_score=-0.9)

    hints = optimization_service.propose_next_attributes(db_session, simulation.id)

    assert hints["anchor_seed"] == 111  # variant[0] scored higher, its anchor should be proposed
    assert hints["perturbation_radius"] == optimization_service._NUDGED_PERTURBATION_RADIUS
    assert hints["hue_shift_center_degrees"] == 45
