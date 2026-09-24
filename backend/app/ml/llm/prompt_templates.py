"""Builds the full persona-reaction prompt for Step 21's simulation service,
combining a Persona's base prompt_template, a ProductVariant's attributes,
and a Simulation's scenario fields (pricing/demographic/messaging), and
parses the model's structured response. Follows the example prompt
structure PRD Sec15 gives ("Persona: ...; Income: ...; Preference: ...;
Behavior: ...") -> qualitative reaction + purchase likelihood.
"""

import json
import re
from typing import Optional

REACTION_TEXT_MAX_CHARS = 1000

# The same contract parse_persona_reaction() enforces below, expressed as a
# JSON schema. Providers that support schema-constrained decoding (Ollama's
# `format` parameter) use this to make invalid output impossible at inference
# time rather than something to detect and recover from afterwards. Kept here,
# next to the parser, so the two can't drift apart.
PERSONA_REACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "reaction_text": {"type": "string"},
        "purchase_likelihood": {"type": "number"},
    },
    "required": ["reaction_text", "purchase_likelihood"],
}


# Hue rotation in degrees -> the colour a shopper would actually name. The
# generator produces variants by rotating hue around the product's own base
# colour, so these are approximate families, not exact colour names; the
# wording stays hedged ("shifted toward") rather than asserting a precise shade.
_HUE_NAMES = [
    (0, "the original colourway"),
    (30, "a warmer, more orange-toned colourway"),
    (60, "a yellow-toned colourway"),
    (120, "a green-toned colourway"),
    (180, "a cyan/teal-toned colourway"),
    (240, "a blue-toned colourway"),
    (300, "a purple/magenta-toned colourway"),
]


def describe_variant_for_persona(variant_attributes: dict) -> str:
    """Render a variant as design language a shopper could react to.

    Raw `ProductVariant.attributes` is generator bookkeeping -- anchor_seed,
    perturbation_radius, generation_method, and a `note` describing
    latent-space perturbation. Passing that dict into the prompt verbatim
    (as this module originally did) asks the persona to react to the
    implementation rather than the product, and they did: one recorded
    reaction reads "I'm not impressed by this product design variant. The use
    of latent-space perturbation...". Since every downstream stage --
    sentiment, risk, optimisation scoring, the PMF score and the final
    recommendation -- is computed from that feedback, the whole chain was
    grading reactions to jargon.

    Only fields a shopper could plausibly perceive are surfaced. Seeds and
    method names are dropped rather than reworded, because there is no
    shopper-meaningful version of them.
    """
    parts: list[str] = []

    hue = variant_attributes.get("color_hue_shift_degrees")
    if hue is not None:
        try:
            hue_value = float(hue) % 360
        except (TypeError, ValueError):
            hue_value = None
        if hue_value is not None:
            closest = min(_HUE_NAMES, key=lambda pair: min(
                abs(hue_value - pair[0]), 360 - abs(hue_value - pair[0])
            ))
            parts.append(f"Colour: {closest[1]}")

    index = variant_attributes.get("perturbation_index")
    if index is not None:
        # 1-based: "design variation 1" reads naturally, "variation 0" does not.
        parts.append(f"Design variation {int(index) + 1} of the base product, "
                     "with subtly different shaping and surface texture")

    if variant_attributes.get("nudged_from_prior_round"):
        parts.append("Refined from an earlier round based on customer feedback")

    # Any genuinely descriptive attributes a future generator adds (color,
    # texture, layout, branding_style -- the vocabulary the schema documents)
    # pass through as-is, since those are already shopper-facing.
    for key in ("color", "texture", "layout", "branding_style", "material"):
        value = variant_attributes.get(key)
        if value:
            parts.append(f"{key.replace('_', ' ').capitalize()}: {value}")

    if not parts:
        return "A design variation of the product."
    return "; ".join(parts)


def build_persona_reaction_prompt(
    persona_prompt_template: str,
    variant_attributes: dict,
    pricing_strategy: dict,
    target_demographic: dict,
    promotional_messaging: Optional[str],
) -> str:
    scenario_lines = [
        f"- Pricing strategy: {json.dumps(pricing_strategy)}",
        f"- Target demographic (as configured for this simulation): {json.dumps(target_demographic)}",
    ]
    if promotional_messaging:
        scenario_lines.append(f"- Promotional messaging: {promotional_messaging}")

    return (
        f"{persona_prompt_template}\n\n"
        "You are reacting, in character as this persona, to a product design variant "
        "being considered for launch.\n"
        f"The design variant: {describe_variant_for_persona(variant_attributes)}\n"
        "Launch scenario:\n" + "\n".join(scenario_lines) + "\n\n"
        "Respond with ONLY a JSON object (no other text, no markdown code fences) "
        "with exactly these two fields:\n"
        '{"reaction_text": "<2-3 sentences of qualitative reaction, in character as this persona>", '
        '"purchase_likelihood": <float between 0.0 and 1.0>}'
    )


class PersonaReactionParseError(Exception):
    pass


def parse_persona_reaction(raw_completion: str) -> dict:
    """Parses the model's response into {"reaction_text": str, "purchase_likelihood": float}.
    Tolerates the model wrapping the JSON in a markdown code fence despite being
    asked not to, since that's a common, harmless LLM habit worth handling
    rather than treating as a hard failure."""
    text = raw_completion.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise PersonaReactionParseError(f"Model response was not valid JSON: {raw_completion!r}") from e

    if "reaction_text" not in data or "purchase_likelihood" not in data:
        raise PersonaReactionParseError(f"Model response missing required fields: {data!r}")

    reaction_text = str(data["reaction_text"])[:REACTION_TEXT_MAX_CHARS]

    try:
        purchase_likelihood = float(data["purchase_likelihood"])
    except (TypeError, ValueError) as e:
        raise PersonaReactionParseError(f"purchase_likelihood was not a number: {data['purchase_likelihood']!r}") from e
    purchase_likelihood = max(0.0, min(1.0, purchase_likelihood))

    return {"reaction_text": reaction_text, "purchase_likelihood": purchase_likelihood}
