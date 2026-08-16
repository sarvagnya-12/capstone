"""Implements FR#7 (PRD Sec9): rule-based risk detection. Threshold-based
and rule-based only, per PRD's own wording ("rule-based + AI insights") --
no anomaly-detection model is trained. Evaluates each variant's aggregated
Feedback rows against 4 explicit, documented rules; each triggered rule
appends a structured {rule, severity, detail} entry.

Risk flags are stored on Feedback.risk_flags, denormalized across every
Feedback row belonging to the variant, rather than a dedicated variant-level
field -- ProductVariant has no risk_flags column in the current schema, and
adding one is outside this step's own file list (services/risk_service.py
only). A disclosed schema-driven choice, not a silent shortcut.

Correction to this step's own plan text: it describes "an unusually LOW
fid_score ... indicating a possibly unrealistic variant" -- this is backwards
from how FID actually works and from what Step 18 itself verified (a
degraded/less-realistic batch scored HIGHER: 409 vs. 131 for a normal batch).
This implementation flags unusually HIGH fid_score instead, consistent with
Step 18's own confirmed behavior.
"""

import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.feedback import Feedback, SentimentLabel
from app.models.product_variant import ProductVariant

# Threshold constants -- documented, not magic numbers scattered through the
# function. Loosely calibrated (no labeled risk dataset exists yet to tune
# these against); a starting point subject to revision once real usage data
# exists.
NEGATIVE_SENTIMENT_RATIO_THRESHOLD = 0.5
LOW_PURCHASE_LIKELIHOOD_THRESHOLD = 0.3
HIGH_CONSISTENCY_VARIANCE_THRESHOLD = 0.5
HIGH_FID_SCORE_THRESHOLD = 300.0


def detect_risks(db: Session, simulation_id: uuid.UUID) -> dict[uuid.UUID, list[dict]]:
    feedback_rows = list(db.execute(select(Feedback).where(Feedback.simulation_id == simulation_id)).scalars().all())

    by_variant: dict[uuid.UUID, list[Feedback]] = defaultdict(list)
    for feedback in feedback_rows:
        by_variant[feedback.variant_id].append(feedback)

    results: dict[uuid.UUID, list[dict]] = {}
    for variant_id, rows in by_variant.items():
        flags = []

        classified = [r for r in rows if r.sentiment_label is not None]
        if classified:
            negative_ratio = sum(1 for r in classified if r.sentiment_label == SentimentLabel.NEGATIVE) / len(classified)
            if negative_ratio > NEGATIVE_SENTIMENT_RATIO_THRESHOLD:
                flags.append({
                    "rule": "high_negative_sentiment_ratio",
                    "severity": "high",
                    "detail": (
                        f"{negative_ratio:.0%} of {len(classified)} classified reactions were negative "
                        f"(threshold {NEGATIVE_SENTIMENT_RATIO_THRESHOLD:.0%})"
                    ),
                })

        likelihoods = [r.purchase_likelihood for r in rows if r.purchase_likelihood is not None]
        if likelihoods:
            avg_likelihood = sum(likelihoods) / len(likelihoods)
            if avg_likelihood < LOW_PURCHASE_LIKELIHOOD_THRESHOLD:
                flags.append({
                    "rule": "low_purchase_likelihood",
                    "severity": "high",
                    "detail": (
                        f"average purchase_likelihood {avg_likelihood:.2f} is below threshold "
                        f"{LOW_PURCHASE_LIKELIHOOD_THRESHOLD:.2f}"
                    ),
                })

        variances = [r.consistency_variance for r in rows if r.consistency_variance is not None]
        if variances:
            avg_variance = sum(variances) / len(variances)
            if avg_variance > HIGH_CONSISTENCY_VARIANCE_THRESHOLD:
                flags.append({
                    "rule": "unreliable_persona_signal",
                    "severity": "medium",
                    "detail": (
                        f"average consistency_variance {avg_variance:.2f} exceeds threshold "
                        f"{HIGH_CONSISTENCY_VARIANCE_THRESHOLD:.2f} -- persona responses were not stable on re-check"
                    ),
                })

        variant = db.get(ProductVariant, variant_id)
        if variant is not None and variant.fid_score is not None and variant.fid_score > HIGH_FID_SCORE_THRESHOLD:
            flags.append({
                "rule": "low_realism_fid",
                "severity": "medium",
                "detail": (
                    f"FID score {variant.fid_score:.1f} exceeds threshold {HIGH_FID_SCORE_THRESHOLD:.1f} "
                    "-- variant may be visually unrealistic"
                ),
            })

        results[variant_id] = flags
        for row in rows:
            row.risk_flags = flags if flags else None

    db.commit()
    return results
