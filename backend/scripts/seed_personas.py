"""Derives candidate persona attribute segments (age range, income, lifestyle,
region) either from real ref_product_intelligence data (once the dataset
pipeline has been run for real) or from a hand-authored baseline list, and
seeds the `personas` table from them (Step 19) -- so the persona-template
library always has ~20 usable, structured templates to build from, regardless
of how much real pipeline data currently exists (resolves Decision #4:
avoids being limited to the 2-3 hand-picked examples in the source diagrams).

Run directly to (re-)seed:
    python -m scripts.seed_personas
"""

import hashlib
import re

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.persona import Persona, PersonaSource
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


# Behavior description per lifestyle -- feeds both `behavior_traits` (JSON)
# and `prompt_template` (text). Follows PRD Sec15's example prompt structure
# ("Persona: {trait}; Income: {level}; Preference: {pref}; Behavior:
# {behavior}"). A generic fallback covers lifestyle strings not in this
# lookup (expected once real ref_product_intelligence data exists, since its
# `target_lifestyle` values aren't constrained to this controlled vocabulary).
_BEHAVIOR_BY_LIFESTYLE: dict[str, dict] = {
    "Student / Budget-conscious": {
        "price_sensitivity": "high",
        "behavior": "compares price first, seeks discounts and student offers, influenced by peer/social trends",
    },
    "Urban Professional": {
        "price_sensitivity": "moderate",
        "behavior": "values quality and convenience, moderate price sensitivity, brand-conscious",
    },
    "Trend-driven Buyer": {
        "price_sensitivity": "moderate",
        "behavior": "follows social media and trends closely, early adopter, responsive to novelty and limited releases",
    },
    "Budget Shopper": {
        "price_sensitivity": "high",
        "behavior": "highly price-sensitive, compares multiple options before buying, waits for sales/discounts",
    },
    "Premium User": {
        "price_sensitivity": "low",
        "behavior": "prioritizes quality, craftsmanship, and exclusivity; low price sensitivity; brand loyal",
    },
    "Athletic / Active": {
        "price_sensitivity": "moderate",
        "behavior": "values performance and durability, researches technical specs and reviews before buying",
    },
    "Family-focused": {
        "price_sensitivity": "moderate",
        "behavior": "prioritizes practicality and value for money, weighs durability and versatility",
    },
    "Established / Luxury": {
        "price_sensitivity": "low",
        "behavior": "seeks premium/luxury positioning and brand heritage, largely price-insensitive",
    },
}
_DEFAULT_BEHAVIOR = {
    "price_sensitivity": "moderate",
    "behavior": "evaluates price, quality, and brand reputation before purchasing",
}


def _slugify(*parts: object) -> str:
    text = "_".join(str(p) for p in parts if p is not None).lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text


def build_persona_row(segment: dict, source: str) -> dict:
    """Converts one segment dict (age_min/age_max/gender/income_segment/
    region/lifestyle) into a full Persona-ready dict."""
    lifestyle = segment["lifestyle"]
    behavior_info = _BEHAVIOR_BY_LIFESTYLE.get(lifestyle, _DEFAULT_BEHAVIOR)

    template_key = _slugify(lifestyle, segment["region"], segment["age_min"], segment["age_max"])
    # Real segments can collide on the above (e.g. duplicate rows across
    # products with the same target segment) -- disambiguate deterministically
    # rather than relying on caller-side dedup.
    if source == "real":
        digest = hashlib.sha256(repr(sorted(segment.items())).encode()).hexdigest()[:8]
        template_key = f"{template_key}_{digest}"

    name = f"{lifestyle} ({segment['region']}, {segment['age_min']}-{segment['age_max']})"

    prompt_template = (
        f"Persona: {lifestyle}; Age: {segment['age_min']}-{segment['age_max']}; "
        f"Income: {segment['income_segment']}; Region: {segment['region']}; "
        f"Behavior: {behavior_info['behavior']}"
    )

    return {
        "template_key": template_key,
        "name": name,
        "age_min": segment["age_min"],
        "age_max": segment["age_max"],
        "income_segment": segment["income_segment"],
        "lifestyle": lifestyle,
        "region": segment["region"],
        "gender": segment.get("gender"),
        "behavior_traits": {
            "price_sensitivity": behavior_info["price_sensitivity"],
            "description": behavior_info["behavior"],
        },
        "prompt_template": prompt_template,
        "source": PersonaSource.SEEDED if source != "dynamic" else PersonaSource.DYNAMIC,
    }


def seed_personas(db: Session) -> tuple[list[dict], str]:
    """Idempotent: upserts by template_key, so re-running updates existing
    rows (e.g. after a baseline-list edit) instead of duplicating them."""
    segments, source = get_persona_segments(db)
    rows = [build_persona_row(segment, source) for segment in segments]

    stmt = pg_insert(Persona).values(rows)
    update_columns = {
        c.name: getattr(stmt.excluded, c.name)
        for c in Persona.__table__.columns
        if c.name not in ("id", "template_key", "created_at")
    }
    stmt = stmt.on_conflict_do_update(index_elements=["template_key"], set_=update_columns)
    db.execute(stmt)
    db.commit()

    return rows, source


def main() -> None:
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        rows, source = seed_personas(db)
        count = db.execute(select(Persona)).scalars().all()
        print(f"Seeded {len(rows)} personas from {source} segments ({len(count)} total rows in personas table).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
