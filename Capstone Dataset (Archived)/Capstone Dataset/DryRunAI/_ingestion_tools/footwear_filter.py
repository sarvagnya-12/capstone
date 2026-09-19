"""Heuristic footwear filter for Amazon Reviews 2023 metadata.

WHY THIS EXISTS AND WHAT IT IS NOT
----------------------------------
Amazon Reviews 2023 has no shoes-only subset -- footwear is bundled inside
"Clothing_Shoes_and_Jewelry" together with apparel, bags and jewelry. There is no
ground-truth footwear label anywhere in the source data, so isolating shoes
requires a heuristic. This is an approximation, not ground truth: `classify()`
returns the reason for every decision so the acquisition script can write a
report with real counts and sampled examples, keeping the filter's imprecision
visible and auditable rather than hidden behind a row count.

HOW IT DECIDES
--------------
`categories` is an ordered taxonomy path, e.g.
    ['Clothing, Shoes & Jewelry', 'Women', 'Shoes', 'Sandals', 'Flats']
Element 0 is a constant root present on every record in this category dump, so
it carries no signal and is discarded -- matching substrings against the joined
path (an earlier version of this filter did exactly that) makes every single
product look like both a shoe and a piece of jewelry.

The remaining path segments are the authoritative signal: Amazon files footwear
under a literal 'Shoes' node (or a footwear-type node such as 'Sandals'). The
product title is consulted only when the category path gives no verdict, since
titles are marketing copy and mention shoes in plenty of things that are not
shoes.
"""

from __future__ import annotations

from dataclasses import dataclass

# Category path segments that mean "this is footwear". Matched as whole
# segments, not substrings.
FOOTWEAR_SEGMENTS = frozenset(
    {
        "shoes",
        "sandals",
        "boots",
        "sneakers",
        "slippers",
        "athletic",
        "athletic shoes",
        "work & safety shoes",
        "loafers & slip-ons",
        "flats",
        "pumps",
        "heels",
        "clogs & mules",
        "oxfords",
    }
)

# Whole segments that mean "definitely not footwear". Only consulted when no
# footwear segment is present, so 'Women > Shoes > ...' is never overridden.
NON_FOOTWEAR_SEGMENTS = frozenset(
    {
        "jewelry",
        "watches",
        "handbags & wallets",
        "clothing",
        "sunglasses",
        "eyewear",
        "luggage & travel gear",
        "accessories",
        "shoe, jewelry & watch accessories",
    }
)

# Shoe-adjacent products that are NOT shoes. Checked first, against both the
# title and the deeper path segments, because most contain a footwear word by
# construction ("shoe rack", "boot cuff", "sneaker cleaner").
EXCLUSION_TERMS = (
    "shoe care",
    "shoe rack",
    "shoe tree",
    "shoe horn",
    "shoe bag",
    "shoe box",
    "shoe organizer",
    "shoe cleaner",
    "shoe polish",
    "shoe brush",
    "shoe insert",
    "shoe cover",
    "shoe stretcher",
    "shoe deodorizer",
    "shoe charm",
    "shoe lace",
    "shoelace",
    "shoestring",
    "insole",
    "arch support",
    "boot cuff",
    "boot shaper",
    "boot clip",
    "heel grip",
    "heel pad",
    "heel protector",
    "heel cushion",
    "sock",
    "hosiery",
    "tights",
    "legging",
    "shoe polish",
    "replacement laces",
)

# Title keywords, used only as a fallback when the category path is silent.
FOOTWEAR_TITLE_TERMS = (
    "shoe",
    "sneaker",
    "boot",
    "sandal",
    "slipper",
    "loafer",
    "espadrille",
    "moccasin",
    "clog",
    "flip flop",
    "flip-flop",
    "high heel",
    "stiletto",
    "oxford",
)


@dataclass(frozen=True, slots=True)
class Decision:
    keep: bool
    reason: str


def _segments(record: dict) -> list[str]:
    """Taxonomy path segments below the constant root, lowercased."""
    categories = record.get("categories") or []
    if not isinstance(categories, (list, tuple)):
        return []
    return [str(segment).strip().lower() for segment in categories[1:] if str(segment).strip()]


def _contains(text: str, terms) -> str | None:
    for term in terms:
        if term in text:
            return term
    return None


def classify(record: dict) -> Decision:
    """Decide whether one Amazon metadata record is a footwear product."""
    title = str(record.get("title") or "").lower()
    segments = _segments(record)
    segment_blob = " | ".join(segments)

    hit = _contains(title, EXCLUSION_TERMS) or _contains(segment_blob, EXCLUSION_TERMS)
    if hit:
        return Decision(False, f"excluded:{hit}")

    for segment in segments:
        if segment in FOOTWEAR_SEGMENTS:
            return Decision(True, f"category_segment:{segment}")

    for segment in segments:
        if segment in NON_FOOTWEAR_SEGMENTS:
            return Decision(False, f"non_footwear_segment:{segment}")

    hit = _contains(title, FOOTWEAR_TITLE_TERMS)
    if hit:
        return Decision(True, f"title:{hit}")

    return Decision(False, "no_footwear_signal")
