"""Business-facing summary of a completed simulation.

Everything here is derived from data the pipeline already produced
(feedback, sentiment, risk flags, the recommendation's ranking) and re-stated
in terms a product or marketing lead can act on: how many customer profiles
would buy, who an option appeals to, what they objected to, and what to do
next. It is the single source for the dashboard, the PDF and the CSV, so the
three never disagree.

Deliberately NOT shown to business readers: FID, the engagement proxy, the
min-max-normalised "PMF score" (it always puts the best option at 100 and the
worst at 0, even when nobody wanted either -- the average purchase likelihood
is the honest absolute number), internal rule names, IDs and raw JSON.

The thresholds below (what counts as "likely to buy", "strong interest") are
presentation heuristics chosen for readability, not calibrated against real
sales -- the report says so in its disclaimer.
"""

from __future__ import annotations

import re
import uuid
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Optional

import numpy as np
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ml.diffusion.hybrid import colour_phrase
from app.services.storage_service import get_path
from app.models.feedback import Feedback, SentimentLabel
from app.models.persona import Persona
from app.models.product_variant import ProductVariant
from app.models.recommendation import Recommendation
from app.models.simulation import Simulation
from app.services.persona_service import LLM_ERROR_PREFIX

LIKELY_TO_BUY = 0.6
UNLIKELY_TO_BUY = 0.35
STRONG_INTEREST = 60
MODERATE_INTEREST = 40
CLOSE_RACE_POINTS = 5
DISCLAIMER = (
    "These results come from AI-simulated customer profiles reacting to AI-generated design images. "
    "Treat them as directional evidence to guide decisions, not as a forecast of real sales. "
    "Confirm the chosen option with a small real-customer test before a full launch."
)

# Topics customers raise, matched on whole words in their reactions.
THEMES = {
    "Price": r"price|priced|pricing|expensive|cheap|cost|costs|afford|affordable|budget|sale|discount|deal|worth|value|dollars?|euros?|\$",
    "Comfort & fit": r"comfort|comfortable|cushion\w*|support\w*|fit|fits|sizing|arch|wide|narrow",
    "Quality & durability": r"quality|durab\w*|last|lasting|construction|craftsmanship|well-made|flimsy|materials?|stitching|wear",
    "Look & style": r"colou?r\w*|style|stylish|look|looks|design|aesthetic|bold|garish|sleek|trendy|palette|tone",
    "Everyday use": r"everyday|daily|errands|versatile|practical|school|work|commute|walking|running",
}
_THEME_RE = {name: re.compile(rf"(?<![\w-])(?:{pattern})(?![\w-])", re.IGNORECASE) for name, pattern in THEMES.items()}

RISK_TEXT = {
    "low_purchase_likelihood": "Weak buying interest overall: customers rated their chance of buying below {low:.0%} on average.",
    "high_negative_sentiment_ratio": "More than half of the customer comments on this option were critical.",
    "unreliable_persona_signal": "Reactions changed noticeably when customers were asked again, so treat this option's result with extra caution.",
    "low_realism_fid": "The generated image for this option looked unrealistic, which may have lowered customer reactions.",
}


@dataclass
class CustomerReaction:
    profile: str
    buying_intent: str  # "Likely to buy" / "Undecided" / "Unlikely to buy"
    likelihood_pct: int
    reaction: str  # tone of the comment: "Positive" / "Neutral" / "Critical" / "Not classified"
    comment: str


@dataclass
class OptionInsight:
    variant_id: str
    label: str  # "Option A"
    colourway: str
    rank: int
    is_recommended: bool
    purchase_intent_pct: int
    interest_level: str  # "Strong" / "Moderate" / "Low"
    likely_buyers: int
    undecided: int
    unlikely_buyers: int
    profiles: int
    liked: int
    neutral: int
    disliked: int
    reception: str  # "Mostly positive" / "Mixed" / "Mostly critical"
    appeals_most_to: list[str]
    least_interested: list[str]
    best_quote: Optional[CustomerReaction]
    worst_quote: Optional[CustomerReaction]
    concerns: list[str]
    themes: list[dict]  # [{"topic": "Price", "mentions": 4}]
    reactions: list[CustomerReaction] = field(default_factory=list)


@dataclass
class SimulationInsights:
    product_name: str
    product_brand: Optional[str]
    product_category: Optional[str]
    price_text: str
    audience_text: str
    messaging: Optional[str]
    profiles_tested: int
    options_tested: int
    rounds_run: int
    verdict: str  # one-line answer
    bottom_line: str  # 2-3 sentence summary
    recommended_label: str
    options: list[OptionInsight]
    next_steps: list[str]
    disclaimer: str = DISCLAIMER

    def to_dict(self) -> dict:
        return asdict(self)


class InsightsUnavailableError(Exception):
    pass


# Hue upper bounds in degrees. Purple reaches 320 because magenta-purple
# product renders measured at ~311 read as purple, not pink.
_HUE_BANDS = [(15, "red"), (40, "orange"), (65, "yellow"), (160, "green"), (195, "teal"), (255, "blue"),
              (320, "purple"), (340, "pink"), (360, "red")]


def dominant_colour_name(image: Image.Image) -> Optional[str]:
    """Plain colour name of the product in a photo on a white background,
    measured from the pixels. Needed because the colour the pipeline ASKED
    for is not always what the image model drew (a "original colourway"
    request for a black sneaker came back light grey)."""
    hsv = np.asarray(image.convert("RGB").resize((96, 96)).convert("HSV"), dtype=np.float32) / 255.0
    rgb = np.asarray(image.convert("RGB").resize((96, 96)), dtype=np.float32) / 255.0
    foreground = rgb.min(axis=2) < 0.9  # drop the near-white background
    if foreground.sum() < 50:
        return None
    h, s, v = (hsv[..., i][foreground] for i in range(3))
    sat, val = float(np.median(s)), float(np.median(v))
    if val < 0.22:
        return "black"
    if sat < 0.18:
        return "light grey" if val > 0.7 else "grey" if val > 0.4 else "dark grey"
    coloured = s > 0.18
    hue_deg = float(np.median(h[coloured])) * 360 if coloured.any() else 0.0
    name = next(n for limit, n in _HUE_BANDS if hue_deg <= limit)
    if name in ("orange", "red") and sat < 0.6:
        # Leather browns are warm but far less saturated than a true red:
        # tan boots measured hue ~15, saturation ~0.5, brightness ~0.6.
        name = "tan" if val >= 0.55 else "brown"
    elif val > 0.8 and sat < 0.45:
        name = f"light {name}"
    elif val < 0.5:  # navy renders measured 0.31-0.37, mid-blue 0.79+
        name = f"dark {name}"
    return name


def _colourway(variant: ProductVariant) -> str:
    """Colour as it appears in the generated image; falls back to the colour
    that was requested if the image can't be read."""
    name = None
    try:
        with Image.open(get_path(variant.image_path)) as img:
            name = dominant_colour_name(img)
    except OSError:
        pass
    if name:
        return f"{name[:1].upper()}{name[1:]} colourway"
    phrase = re.sub(r"^(a|an|the)\s+", "", colour_phrase((variant.attributes or {}).get("color_hue_shift_degrees")))
    return phrase[:1].upper() + phrase[1:]


def _price_text(pricing_strategy: dict) -> str:
    tiers = (pricing_strategy or {}).get("tiers") or []
    if not tiers:
        return "Not specified"
    return ", ".join(f"{tier.get('tier_name', 'price').capitalize()}: {float(tier.get('price', 0)):,.2f}" for tier in tiers)


def _audience_text(target: dict) -> str:
    target = target or {}
    parts = []
    if target.get("age_min") or target.get("age_max"):
        parts.append(f"Ages {target.get('age_min', '?')}-{target.get('age_max', '?')}")
    for key in ("gender", "income_segment", "region", "lifestyle"):
        if target.get(key):
            value = str(target[key])
            parts.append(f"{value} income" if key == "income_segment" else value)
    return ", ".join(parts) if parts else "General audience"


def _intent_label(likelihood: float) -> str:
    if likelihood >= LIKELY_TO_BUY:
        return "Likely to buy"
    if likelihood < UNLIKELY_TO_BUY:
        return "Unlikely to buy"
    return "Undecided"


def _reaction_label(label: Optional[SentimentLabel]) -> str:
    # Labels describe the TONE of the comment, which the sentiment model scores --
    # not whether they would buy: "I'm concerned about durability, but the price
    # is fair" is critical in tone from a customer still likely to buy.
    return {SentimentLabel.POSITIVE: "Positive", SentimentLabel.NEGATIVE: "Critical",
            SentimentLabel.NEUTRAL: "Neutral"}.get(label, "Not classified")


def _interest_level(pct: int) -> str:
    return "Strong" if pct >= STRONG_INTEREST else "Moderate" if pct >= MODERATE_INTEREST else "Low"


def _reception(liked: int, neutral: int, disliked: int) -> str:
    total = liked + neutral + disliked
    if not total:
        return "No reactions recorded"
    if liked / total >= 0.6:
        return "Mostly positive"
    if disliked / total > 0.5:  # an even split is "Mixed", not "Mostly critical"
        return "Mostly critical"
    return "Mixed"


def _option_insight(label: str, rank: int, variant: ProductVariant, is_recommended: bool,
                    rows: list[tuple[Feedback, str]]) -> OptionInsight:
    valid = [(fb, name) for fb, name in rows if not (fb.qualitative_text or "").startswith(LLM_ERROR_PREFIX)]
    reactions = [
        CustomerReaction(profile=name, buying_intent=_intent_label(fb.purchase_likelihood),
                         likelihood_pct=round(fb.purchase_likelihood * 100), reaction=_reaction_label(fb.sentiment_label),
                         comment=fb.qualitative_text)
        for fb, name in sorted(valid, key=lambda r: -r[0].purchase_likelihood)
    ]
    likelihoods = [fb.purchase_likelihood for fb, _ in valid]
    pct = round(100 * sum(likelihoods) / len(likelihoods)) if likelihoods else 0
    liked = sum(1 for r in reactions if r.reaction == "Positive")
    disliked = sum(1 for r in reactions if r.reaction == "Critical")
    neutral = sum(1 for r in reactions if r.reaction == "Neutral")

    top = max((fb.purchase_likelihood for fb, _ in valid), default=0.0)
    appeals = [r.profile for r in reactions if r.likelihood_pct / 100 >= max(LIKELY_TO_BUY, top - 0.05)] if top >= UNLIKELY_TO_BUY else []
    least = [r.profile for r in reactions if r.likelihood_pct / 100 < UNLIKELY_TO_BUY]

    theme_counts = Counter()
    price_objections = 0
    for fb, _ in valid:
        text = fb.qualitative_text or ""
        for theme, pattern in _THEME_RE.items():
            if pattern.search(text):
                theme_counts[theme] += 1
        if _THEME_RE["Price"].search(text) and fb.purchase_likelihood < 0.5:
            price_objections += 1

    concerns: list[str] = []
    if valid and price_objections >= max(2, (len(valid) + 1) // 2):
        concerns.append(f"Price is a barrier: {price_objections} of {len(valid)} customer profiles raised price and leaned against buying.")
    seen_rules = set()
    for fb, _ in rows:
        for flag in fb.risk_flags or []:
            rule = flag.get("rule")
            if rule in RISK_TEXT and rule not in seen_rules:
                seen_rules.add(rule)
                concerns.append(RISK_TEXT[rule].format(low=UNLIKELY_TO_BUY))
    if len(valid) < len(rows):
        concerns.append(f"{len(rows) - len(valid)} customer profile(s) gave no usable reaction, so this result rests on fewer opinions.")

    best = reactions[0] if reactions and reactions[0].likelihood_pct >= 50 else None
    worst = reactions[-1] if reactions and reactions[-1].likelihood_pct < 50 else None

    return OptionInsight(
        variant_id=str(variant.id), label=label, colourway=_colourway(variant), rank=rank,
        is_recommended=is_recommended, purchase_intent_pct=pct, interest_level=_interest_level(pct),
        likely_buyers=sum(1 for r in reactions if r.buying_intent == "Likely to buy"),
        undecided=sum(1 for r in reactions if r.buying_intent == "Undecided"),
        unlikely_buyers=sum(1 for r in reactions if r.buying_intent == "Unlikely to buy"),
        profiles=len(reactions), liked=liked, neutral=neutral, disliked=disliked,
        reception=_reception(liked, neutral, disliked), appeals_most_to=appeals, least_interested=least,
        best_quote=best, worst_quote=worst, concerns=concerns,
        themes=[{"topic": t, "mentions": n} for t, n in theme_counts.most_common(3)],
        reactions=reactions,
    )


def _next_steps(options: list[OptionInsight]) -> list[str]:
    best = options[0]
    steps: list[str] = []
    if best.purchase_intent_pct < MODERATE_INTEREST:
        steps.append("No option generated strong buying interest. Revisit the design, price or positioning before committing to a launch.")
    else:
        steps.append(f"Take {best.label} ({best.colourway.lower()}) forward as the lead design.")
    if best.appeals_most_to:
        steps.append("Aim launch marketing first at the customers who responded best: " + ", ".join(best.appeals_most_to[:3]) + ".")
    if any(c.startswith("Price is a barrier") for c in best.concerns):
        steps.append("Price was the most common objection. Test a lower price point or a launch discount in the next simulation.")
    if len(options) > 1 and best.purchase_intent_pct - options[1].purchase_intent_pct < CLOSE_RACE_POINTS:
        steps.append(f"{best.label} and {options[1].label} performed almost the same. Run the simulation again with more "
                     "customer profiles before choosing between them.")
    if any("asked again" in c for o in options for c in o.concerns):
        steps.append("Some customer reactions were inconsistent. Re-run the simulation to confirm the result.")
    steps.append("Validate the chosen option with a small real-customer test (survey or pre-order page) before a full launch.")
    return steps


def build_insights(db: Session, simulation_id: uuid.UUID) -> SimulationInsights:
    simulation = db.get(Simulation, simulation_id)
    recommendation = (db.query(Recommendation).filter(Recommendation.simulation_id == simulation_id).one_or_none()
                      if simulation else None)
    if simulation is None or recommendation is None:
        raise InsightsUnavailableError(f"No completed results for simulation {simulation_id}")

    variant_ids = [uuid.UUID(entry["variant_id"]) for entry in recommendation.ranking]
    variants = {v.id: v for v in db.query(ProductVariant).filter(ProductVariant.id.in_(variant_ids))}
    rows = db.execute(
        select(Feedback, Persona.name).join(Persona, Feedback.persona_id == Persona.id)
        .where(Feedback.simulation_id == simulation_id, Feedback.variant_id.in_(variant_ids))
    ).all()
    by_variant: dict[uuid.UUID, list] = {vid: [] for vid in variant_ids}
    for fb, name in rows:
        by_variant[fb.variant_id].append((fb, name))
    rounds = db.execute(select(func.max(Feedback.iteration_number)).where(Feedback.simulation_id == simulation_id)).scalar()

    # Keep the system's own ranking and recommendation (it weighs purchase
    # intent together with sentiment and risk flags); the business view only
    # re-labels it. Option A is always the recommended one.
    options = [
        _option_insight(f"Option {chr(ord('A') + index)}", index + 1, variants[vid],
                        vid == recommendation.recommended_variant_id, by_variant[vid])
        for index, vid in enumerate(v for v in variant_ids if v in variants)
    ]
    if not options:
        raise InsightsUnavailableError(f"No variants found for simulation {simulation_id}")

    best = options[0]
    verdict = {
        "Strong": f"{best.label} is a strong launch candidate.",
        "Moderate": f"{best.label} is promising but needs refinement before launch.",
        "Low": "None of the tested options is launch-ready yet.",
    }[best.interest_level]
    bottom_line = (
        f"{best.label} ({best.colourway.lower()}) performed best: {best.likely_buyers} of {best.profiles} customer "
        f"profiles said they would likely buy it, with an average purchase likelihood of {best.purchase_intent_pct}%. "
        f"The tone of customer comments was {best.reception.lower()}."
    )
    if len(options) > 1:
        runner = options[1]
        gap = best.purchase_intent_pct - runner.purchase_intent_pct
        if gap >= CLOSE_RACE_POINTS:
            bottom_line += f" It led {runner.label} by {gap} percentage points."
        elif gap >= 0:
            bottom_line += f" {runner.label} was close behind ({runner.purchase_intent_pct}%)."
        else:
            # The ranking also weighs how positive reactions were and any
            # concerns raised, so the top option is not always the one with
            # the highest purchase likelihood -- say why, rather than look wrong.
            bottom_line += (f" {runner.label} had a slightly higher purchase likelihood ({runner.purchase_intent_pct}%), "
                            f"but {best.label} was recommended because customer comments about it were more positive "
                            f"overall and it raised fewer concerns.")

    product = simulation.product
    personas = {name for _, name in rows}
    return SimulationInsights(
        product_name=product.name, product_brand=product.brand, product_category=product.category,
        price_text=_price_text(simulation.pricing_strategy), audience_text=_audience_text(simulation.target_demographic),
        messaging=simulation.promotional_messaging, profiles_tested=len(personas), options_tested=len(options),
        rounds_run=(rounds or 0) + 1, verdict=verdict, bottom_line=bottom_line, recommended_label=best.label,
        options=options, next_steps=_next_steps(options),
    )
