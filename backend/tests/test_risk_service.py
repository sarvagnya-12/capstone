"""Step 24: rule-based risk detection. Each of the 4 documented threshold
rules gets a test that actually crosses its threshold, plus one confirming
no flags fire when everything is comfortably inside bounds."""

from app.models.feedback import SentimentLabel
from app.services import risk_service
from tests.conftest import make_feedback, make_persona, make_simulation_with_variants


def _rule_names(flags):
    return {f["rule"] for f in flags}


def test_no_flags_when_all_metrics_healthy(db_session):
    simulation, variants = make_simulation_with_variants(db_session, n_variants=1)
    persona = make_persona(db_session)
    make_feedback(
        db_session, simulation, variants[0], persona,
        purchase_likelihood=0.8, sentiment_label=SentimentLabel.POSITIVE, sentiment_score=0.9,
    )

    results = risk_service.detect_risks(db_session, simulation.id)

    assert results[variants[0].id] == []


def test_high_negative_sentiment_ratio_triggers(db_session):
    simulation, variants = make_simulation_with_variants(db_session, n_variants=1)
    persona = make_persona(db_session)
    for _ in range(3):
        make_feedback(
            db_session, simulation, variants[0], persona,
            purchase_likelihood=0.8, sentiment_label=SentimentLabel.NEGATIVE, sentiment_score=-0.9,
        )
    make_feedback(
        db_session, simulation, variants[0], persona,
        purchase_likelihood=0.8, sentiment_label=SentimentLabel.POSITIVE, sentiment_score=0.9,
    )

    results = risk_service.detect_risks(db_session, simulation.id)

    assert "high_negative_sentiment_ratio" in _rule_names(results[variants[0].id])


def test_low_purchase_likelihood_triggers(db_session):
    simulation, variants = make_simulation_with_variants(db_session, n_variants=1)
    persona = make_persona(db_session)
    make_feedback(db_session, simulation, variants[0], persona, purchase_likelihood=0.05)

    results = risk_service.detect_risks(db_session, simulation.id)

    assert "low_purchase_likelihood" in _rule_names(results[variants[0].id])


def test_unreliable_persona_signal_triggers(db_session):
    simulation, variants = make_simulation_with_variants(db_session, n_variants=1)
    persona = make_persona(db_session)
    make_feedback(db_session, simulation, variants[0], persona, purchase_likelihood=0.8, consistency_variance=0.9)

    results = risk_service.detect_risks(db_session, simulation.id)

    assert "unreliable_persona_signal" in _rule_names(results[variants[0].id])


def test_low_realism_fid_triggers(db_session):
    simulation, variants = make_simulation_with_variants(db_session, n_variants=1)
    variants[0].fid_score = 450.0
    db_session.flush()
    persona = make_persona(db_session)
    make_feedback(db_session, simulation, variants[0], persona, purchase_likelihood=0.8)

    results = risk_service.detect_risks(db_session, simulation.id)

    assert "low_realism_fid" in _rule_names(results[variants[0].id])


def test_risk_flags_denormalized_across_all_rows_for_variant(db_session):
    simulation, variants = make_simulation_with_variants(db_session, n_variants=1)
    persona = make_persona(db_session)
    f1 = make_feedback(db_session, simulation, variants[0], persona, purchase_likelihood=0.05)
    f2 = make_feedback(db_session, simulation, variants[0], persona, purchase_likelihood=0.05)

    risk_service.detect_risks(db_session, simulation.id)

    db_session.refresh(f1)
    db_session.refresh(f2)
    assert f1.risk_flags == f2.risk_flags
    assert f1.risk_flags is not None
