"""Tests for persona-prompt construction (Step 20).

The central concern here is that the persona sees the *product*, not the
generator's internals. `ProductVariant.attributes` is bookkeeping --
anchor_seed, perturbation_radius, generation_method and a note about
latent-space perturbation -- and an earlier version of the prompt builder
dumped that dict in verbatim. Personas duly reacted to it: a recorded run
produced "I'm not impressed by this product design variant. The use of
latent-space perturbation...". Every downstream stage (sentiment, risk,
optimisation scoring, PMF score, recommendation) derives from that feedback,
so the leak quietly corrupted the whole chain's meaning while everything
still "worked".
"""

import pytest

from app.ml.llm.prompt_templates import (
    build_persona_reaction_prompt,
    describe_variant_for_persona,
    parse_persona_reaction,
)

# Verbatim from a real simulation's product_variants.attributes column.
REAL_VARIANT_ATTRIBUTES = {
    "note": (
        "layout/texture varied via nearby latent-space perturbation (undifferentiated "
        "structural variation, not a disentangled single-axis control); color varied via "
        "real HSV hue-shift post-processing; branding_style carries no semantic meaning "
        "on this generic pretrained checkpoint"
    ),
    "anchor_seed": 733873630,
    "generation_method": "gan_latent_variation",
    "perturbation_index": 1,
    "perturbation_radius": 0.4,
    "branding_seed_offset": 1,
    "color_hue_shift_degrees": 120.0,
    "nudged_from_prior_round": False,
}

JARGON = [
    "latent",
    "perturbation",
    "anchor_seed",
    "generation_method",
    "gan_latent",
    "checkpoint",
    "branding_seed_offset",
    "hue_shift",
    "HSV",
]


def test_prompt_contains_no_generator_internals():
    prompt = build_persona_reaction_prompt(
        persona_prompt_template="You are Priya, a budget-conscious commuter.",
        variant_attributes=REAL_VARIANT_ATTRIBUTES,
        pricing_strategy={"tiers": [{"tier_name": "standard", "price": 129.99}]},
        target_demographic={"region": "US"},
        promotional_messaging=None,
    )
    leaked = [term for term in JARGON if term.lower() in prompt.lower()]
    assert not leaked, f"generator internals reached the persona prompt: {leaked}"


def test_hue_shift_becomes_a_colour_a_shopper_could_name():
    assert "green" in describe_variant_for_persona({"color_hue_shift_degrees": 120.0}).lower()
    assert "blue" in describe_variant_for_persona({"color_hue_shift_degrees": 240.0}).lower()
    # 0 degrees is the unmodified product, not a "0-degree shift".
    assert "original" in describe_variant_for_persona({"color_hue_shift_degrees": 0.0}).lower()


def test_hue_wraps_around_the_colour_wheel():
    """350 deg is a hair below 360, so it must read as the original colour
    rather than snapping to the far end of the table."""
    assert "original" in describe_variant_for_persona({"color_hue_shift_degrees": 350.0}).lower()


def test_variation_index_is_one_based():
    """'Design variation 0' is machine-speak; shoppers count from 1."""
    assert "variation 1" in describe_variant_for_persona({"perturbation_index": 0})
    assert "variation 3" in describe_variant_for_persona({"perturbation_index": 2})


def test_refined_variants_say_so():
    text = describe_variant_for_persona({"perturbation_index": 0, "nudged_from_prior_round": True})
    assert "earlier round" in text.lower()


def test_descriptive_attributes_pass_through_unchanged():
    """A future generator emitting real design vocabulary should surface it
    directly rather than have it dropped by the allow-list."""
    text = describe_variant_for_persona({"color": "matte black", "material": "suede"})
    assert "matte black" in text
    assert "suede" in text


def test_empty_attributes_still_yield_usable_text():
    text = describe_variant_for_persona({})
    assert text.strip()
    assert not any(term in text.lower() for term in JARGON)


@pytest.mark.parametrize("bad", [None, "not-a-number", float("nan")])
def test_malformed_hue_does_not_crash_the_prompt(bad):
    """Attributes come from the DB as JSON; a bad value must not take down a
    whole simulation, since prompt construction happens per persona x variant."""
    text = describe_variant_for_persona({"color_hue_shift_degrees": bad, "perturbation_index": 0})
    assert "variation 1" in text


def test_parse_round_trips_a_realistic_model_response():
    parsed = parse_persona_reaction(
        '{"reaction_text": "The green is bolder than I\'d wear daily.", "purchase_likelihood": 0.3}'
    )
    assert parsed["purchase_likelihood"] == pytest.approx(0.3)
    assert "green" in parsed["reaction_text"]
