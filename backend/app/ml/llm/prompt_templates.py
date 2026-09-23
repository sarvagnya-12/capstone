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
        f"Product variant attributes: {json.dumps(variant_attributes)}\n"
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
