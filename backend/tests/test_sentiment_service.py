"""Step 23: NLP sentiment classification. Uses the real, already-cached
cardiffnlp/twitter-roberta-base-sentiment-latest model -- no external API,
no mocking needed, and this is exactly the kind of real integration worth
proving actually works end-to-end."""

from app.models.feedback import SentimentLabel
from app.services import sentiment_service
from tests.conftest import make_feedback, make_persona, make_simulation_with_variants


def test_classify_feedback_labels_positive_and_negative_text(db_session):
    simulation, variants = make_simulation_with_variants(db_session, n_variants=1)
    persona = make_persona(db_session)
    positive = make_feedback(
        db_session, simulation, variants[0], persona,
        qualitative_text="I absolutely love this, it's fantastic and I would buy it immediately.",
    )
    negative = make_feedback(
        db_session, simulation, variants[0], persona,
        qualitative_text="This is terrible, overpriced, and I hate the design.",
    )

    sentiment_service.classify_feedback(db_session, simulation.id)

    db_session.refresh(positive)
    db_session.refresh(negative)
    assert positive.sentiment_label == SentimentLabel.POSITIVE
    assert positive.sentiment_score > 0
    assert negative.sentiment_label == SentimentLabel.NEGATIVE
    assert negative.sentiment_score < 0


def test_classify_feedback_only_processes_unclassified_rows(db_session):
    simulation, variants = make_simulation_with_variants(db_session, n_variants=1)
    persona = make_persona(db_session)
    already_done = make_feedback(
        db_session, simulation, variants[0], persona,
        qualitative_text="whatever text",
        sentiment_label=SentimentLabel.NEUTRAL, sentiment_score=0.0,
    )

    processed = sentiment_service.classify_feedback(db_session, simulation.id)

    assert already_done.id not in [f.id for f in processed]
    db_session.refresh(already_done)
    assert already_done.sentiment_label == SentimentLabel.NEUTRAL  # untouched, not re-classified
