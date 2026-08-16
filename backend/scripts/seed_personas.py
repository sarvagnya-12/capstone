"""Derives candidate persona attribute segments (age range, income, lifestyle,
region) either from real ref_product_intelligence data (once the dataset
pipeline has been run for real) or from a hand-authored baseline list -- so
Step 19's persona-template library always has ~20 usable segments to build
from, regardless of how much real pipeline data currently exists.

This step only builds the extraction/derivation logic; Step 19 is where the
`personas` table itself actually gets populated using it.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.reference_data import RefProductIntelligence

MIN_REAL_SEGMENTS = 15

# Hand-authored baseline, used whenever ref_product_intelligence doesn't yet
# have enough real distinct segments (true today -- the dataset pipeline has
# generated no real data yet). The concrete examples named across the source
# diagrams (price-sensitive student, urban professional, trend-driven buyer,
# budget shopper, premium user) are represented, then systematically expanded
# across age range x income segment x lifestyle x region, so coverage is
# structured rather than arbitrary.
BASELINE_SEGMENTS: list[dict] = [
    {"age_min": 18, "age_max": 24, "gender": None, "income_segment": "Low", "region": "US", "lifestyle": "Student / Budget-conscious"},
    {"age_min": 18, "age_max": 24, "gender": None, "income_segment": "Low", "region": "EU", "lifestyle": "Student / Budget-conscious"},
    {"age_min": 22, "age_max": 30, "gender": None, "income_segment": "Middle", "region": "US", "lifestyle": "Urban Professional"},
    {"age_min": 22, "age_max": 30, "gender": None, "income_segment": "Middle", "region": "EU", "lifestyle": "Urban Professional"},
    {"age_min": 25, "age_max": 34, "gender": None, "income_segment": "Middle", "region": "APAC", "lifestyle": "Urban Professional"},
    {"age_min": 18, "age_max": 28, "gender": None, "income_segment": "Middle", "region": "US", "lifestyle": "Trend-driven Buyer"},
    {"age_min": 18, "age_max": 28, "gender": None, "income_segment": "Middle", "region": "APAC", "lifestyle": "Trend-driven Buyer"},
    {"age_min": 25, "age_max": 40, "gender": None, "income_segment": "Low", "region": "US", "lifestyle": "Budget Shopper"},
    {"age_min": 25, "age_max": 40, "gender": None, "income_segment": "Low", "region": "EU", "lifestyle": "Budget Shopper"},
    {"age_min": 30, "age_max": 50, "gender": None, "income_segment": "High", "region": "US", "lifestyle": "Premium User"},
    {"age_min": 30, "age_max": 50, "gender": None, "income_segment": "High", "region": "EU", "lifestyle": "Premium User"},
    {"age_min": 30, "age_max": 50, "gender": None, "income_segment": "High", "region": "APAC", "lifestyle": "Premium User"},
    {"age_min": 20, "age_max": 35, "gender": None, "income_segment": "Middle", "region": "US", "lifestyle": "Athletic / Active"},
    {"age_min": 20, "age_max": 35, "gender": None, "income_segment": "Middle", "region": "EU", "lifestyle": "Athletic / Active"},
    {"age_min": 35, "age_max": 55, "gender": None, "income_segment": "Middle", "region": "US", "lifestyle": "Family-focused"},
    {"age_min": 35, "age_max": 55, "gender": None, "income_segment": "Middle", "region": "EU", "lifestyle": "Family-focused"},
    {"age_min": 45, "age_max": 65, "gender": None, "income_segment": "High", "region": "US", "lifestyle": "Established / Luxury"},
    {"age_min": 18, "age_max": 24, "gender": None, "income_segment": "Middle", "region": "APAC", "lifestyle": "Trend-driven Buyer"},
    {"age_min": 25, "age_max": 34, "gender": None, "income_segment": "Low", "region": "APAC", "lifestyle": "Budget Shopper"},
    {"age_min": 30, "age_max": 45, "gender": None, "income_segment": "Middle", "region": "APAC", "lifestyle": "Urban Professional"},
]


def extract_real_segments(db: Session) -> list[dict]:
    """Distinct, non-null target-segment combinations observed in
    ref_product_intelligence."""
    stmt = (
        select(
            RefProductIntelligence.target_age_min,
            RefProductIntelligence.target_age_max,
            RefProductIntelligence.target_gender,
            RefProductIntelligence.target_income_segment,
            RefProductIntelligence.target_region,
            RefProductIntelligence.target_lifestyle,
        )
        .where(
            RefProductIntelligence.target_age_min.is_not(None),
            RefProductIntelligence.target_age_max.is_not(None),
            RefProductIntelligence.target_income_segment.is_not(None),
            RefProductIntelligence.target_region.is_not(None),
            RefProductIntelligence.target_lifestyle.is_not(None),
        )
        .distinct()
    )
    rows = db.execute(stmt).all()
    return [
        {
            "age_min": r.target_age_min,
            "age_max": r.target_age_max,
            "gender": r.target_gender,
            "income_segment": r.target_income_segment,
            "region": r.target_region,
            "lifestyle": r.target_lifestyle,
        }
        for r in rows
    ]


def get_persona_segments(db: Session, min_real_segments: int = MIN_REAL_SEGMENTS) -> tuple[list[dict], str]:
    """Returns (segments, source) where source is "real" (drawn from
    ref_product_intelligence) or "baseline" (the hand-authored fallback)."""
    real_segments = extract_real_segments(db)
    if len(real_segments) >= min_real_segments:
        return real_segments, "real"
    return BASELINE_SEGMENTS, "baseline"
