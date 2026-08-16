"""Step 21/22: persona-reaction simulation and the consistency check. Includes
a regression test for the real bug found during Step 28's own end-to-end
test: without variant_ids scoping, every later round silently re-simulated
every earlier round's variants too."""

from app.models.feedback import Feedback
from app.models.product_variant import ProductVariant
from app.services import persona_service
from tests.conftest import make_persona, make_simulation_with_variants


def test_simulate_persona_reactions_creates_one_row_per_pair(db_session, fake_llm_provider):
    simulation, variants = make_simulation_with_variants(db_session, n_variants=2)
    persona_a = make_persona(db_session, "Alice")
    persona_b = make_persona(db_session, "Bob")
    simulation.personas = [persona_a, persona_b]
    db_session.flush()

    feedback = persona_service.simulate_persona_reactions(db_session, simulation.id, iteration_number=0)

    assert len(feedback) == 4  # 2 variants x 2 personas
    assert all(f.iteration_number == 0 for f in feedback)
    assert all(f.purchase_likelihood in (0.1, 0.8) for f in feedback)


def test_simulate_persona_reactions_variant_ids_scoping_regression(db_session, fake_llm_provider):
    """Regression test for the real bug Step 28's end-to-end test caught:
    round 2 re-simulated round 1's variants too because the query wasn't
    scoped to "this round's variants," only to "this simulation's
    variants." Confirms the fix (an explicit variant_ids filter) actually
    isolates rounds from each other."""
    simulation, round_1_variants = make_simulation_with_variants(db_session, n_variants=2)
    persona = make_persona(db_session, "Solo")
    simulation.personas = [persona]
    db_session.flush()

    persona_service.simulate_persona_reactions(
        db_session, simulation.id, iteration_number=0, variant_ids=[v.id for v in round_1_variants]
    )

    round_2_variant = ProductVariant(
        product_id=round_1_variants[0].product_id, simulation_id=simulation.id,
        image_path="round2.jpg", attributes={}, generation_method="gan_latent_variation",
    )
    db_session.add(round_2_variant)
    db_session.flush()

    persona_service.simulate_persona_reactions(
        db_session, simulation.id, iteration_number=1, variant_ids=[round_2_variant.id]
    )

    round_2_feedback = db_session.query(Feedback).filter(Feedback.iteration_number == 1).all()
    assert len(round_2_feedback) == 1  # NOT 3 -- the pre-fix bug would have re-simulated round 1's 2 variants too
    assert round_2_feedback[0].variant_id == round_2_variant.id


def test_simulate_persona_reactions_without_llm_key_produces_marked_error_rows(db_session, monkeypatch):
    """No fake_llm_provider fixture here -- exercises the real "no
    ANTHROPIC_API_KEY configured" path (Steps 20-21's disclosed gap):
    confirms it degrades to clearly-marked error rows rather than crashing
    the whole simulation."""
    monkeypatch.setattr("app.core.config.settings.ANTHROPIC_API_KEY", None)
    simulation, variants = make_simulation_with_variants(db_session, n_variants=1)
    persona = make_persona(db_session, "NoKey")
    simulation.personas = [persona]
    db_session.flush()

    feedback = persona_service.simulate_persona_reactions(db_session, simulation.id)

    assert len(feedback) == 1
    assert feedback[0].qualitative_text.startswith(persona_service.LLM_ERROR_PREFIX)
    assert feedback[0].purchase_likelihood == 0.0


def test_select_representative_personas_picks_distinct_lifestyles(db_session):
    make_persona(db_session, "P1", lifestyle="urban")
    make_persona(db_session, "P2", lifestyle="rural")
    make_persona(db_session, "P3", lifestyle="urban")  # same lifestyle as P1
    db_session.flush()

    selected = persona_service.select_representative_personas(db_session, count=5)

    assert len(selected) == 3  # only 3 personas exist total, count=5 is just a cap
    lifestyles = [p.lifestyle for p in selected]
    assert "urban" in lifestyles and "rural" in lifestyles
