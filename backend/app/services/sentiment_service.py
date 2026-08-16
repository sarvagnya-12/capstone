"""Implements FR#6 (PRD Sec9): NLP sentiment classification of persona
feedback text."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.nlp.sentiment import classify_text
from app.models.feedback import Feedback, SentimentLabel


def classify_feedback(db: Session, simulation_id: uuid.UUID) -> list[Feedback]:
    """Classifies every Feedback row for this simulation still missing a
    sentiment_label. sentiment_score is signed: +confidence for positive,
    -confidence for negative, 0.0 for neutral (which has no natural sign)."""
    stmt = select(Feedback).where(
        Feedback.simulation_id == simulation_id,
        Feedback.sentiment_label.is_(None),
    )
    rows = list(db.execute(stmt).scalars().all())

    for feedback in rows:
        label, confidence = classify_text(feedback.qualitative_text)
        feedback.sentiment_label = SentimentLabel(label)
        if label == "positive":
            feedback.sentiment_score = confidence
        elif label == "negative":
            feedback.sentiment_score = -confidence
        else:
            feedback.sentiment_score = 0.0

    db.commit()
    for feedback in rows:
        db.refresh(feedback)
    return rows
