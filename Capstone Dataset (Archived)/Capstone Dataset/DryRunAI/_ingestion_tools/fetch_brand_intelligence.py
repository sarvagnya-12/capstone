"""Fetch real brand facts from the Wikipedia and Wikidata APIs (Stage 5 source).

This is the one genuinely networked collector in the whole ingestion set. The
pipeline ships WikipediaCollector / WikidataCollector classes, but like every
other collector in this project they only parse local files -- nothing ever
called an API. This script does the actual fetching and writes the CSV those
collectors already know how to read.

Both APIs are public, documented and intended for programmatic use, so this is
ordinary API consumption rather than scraping. Wikimedia's User-Agent policy
asks for a descriptive agent identifying the client, which is set below, and
requests are issued one at a time with a small delay.

ONLY REAL VALUES ARE WRITTEN. Fields the APIs do not answer (campaign_name,
marketing_strategy, target_income_segment, ...) are left empty rather than
invented -- a fabricated brand mission would be worse than a blank column.
country_of_origin is emitted only when the fetched country is in the Product
Intelligence service's supported_countries list, since anything else is a
guaranteed `invalid_country_name` rejection.

Output:
  datasets/product_intelligence/raw/brand_facts.csv  (one row per brand)

That file is brand-level. Stage 5 requires a product_id on every record, so
fanout_brand_intelligence.py expands it to one row per product afterwards.

Usage:
    python _ingestion_tools/fetch_brand_intelligence.py
    python _ingestion_tools/fetch_brand_intelligence.py --top-brands 80
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests

csv.field_size_limit(10_000_000)

USER_AGENT = "DryRunAI-Capstone/1.0 (academic research project; contact via repository)"
WIKI_API = "https://en.wikipedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"

MAX_RETRIES = 4


def polite_get(session: requests.Session, url: str, params: dict, delay: float) -> requests.Response:
    """GET with backoff on rate limiting.

    Wikimedia returns 429 when a client requests too fast, and an unthrottled
    run of this script triggers it within ~10 brands (observed: 13 of 15 brands
    failed). Their API etiquette asks clients to back off rather than retry
    immediately, and to honour Retry-After when present, so that is what this
    does instead of hammering through the failures.
    """
    wait = max(delay, 1.0)
    last_error: Exception | None = None

    for attempt in range(MAX_RETRIES):
        try:
            response = session.get(url, params=params, timeout=30)
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                pause = float(retry_after) if retry_after and retry_after.isdigit() else wait
                time.sleep(pause)
                wait = min(wait * 2, 30.0)
                continue
            response.raise_for_status()
            return response
        except requests.RequestException as error:
            last_error = error
            time.sleep(wait)
            wait = min(wait * 2, 30.0)

    raise requests.RequestException(f"giving up after {MAX_RETRIES} attempts: {last_error or 'repeated 429'}")

SUPPORTED_COUNTRIES = {
    "United States",
    "Germany",
    "Japan",
    "India",
    "United Kingdom",
    "Canada",
    "Australia",
}
COUNTRY_ALIASES = {
    "United States of America": "United States",
    "USA": "United States",
    "U.S.": "United States",
    "Federal Republic of Germany": "Germany",
    "West Germany": "Germany",
    "Empire of Japan": "Japan",
    "United Kingdom of Great Britain and Ireland": "United Kingdom",
    "England": "United Kingdom",
}

OUTPUT_COLUMNS = [
    "intelligence_record_id",
    "brand",
    "source",
    "source_url",
    "brand_description",
    "tagline",
    "parent_company",
    "country_of_origin",
    "collected_at",
]



NATIONALITY_TO_COUNTRY = {
    "american": "United States",
    "german": "Germany",
    "japanese": "Japan",
    "british": "United Kingdom",
    "english": "United Kingdom",
    "canadian": "Canada",
    "australian": "Australia",
    "indian": "India",
    "french": "France",
    "danish": "Denmark",
    "south korean": "South Korea",
    "italian": "Italy",
    "swiss": "Switzerland",
    "dutch": "Netherlands",
    "spanish": "Spain",
}


def sanitize_fact(brand: str, description: str, country: str) -> tuple[str, str]:
    """Blank out values the text itself proves wrong. Blank beats wrong.

    Every case here was observed in a real run, not imagined:
      - "Keen, Keen's, or Keens may refer to:"  -> a disambiguation page, not a company
      - "Jessica Ann Johnson (nee Simpson; born July 10, 1980) is..."
                                                 -> the person, not the shoe brand
      - "Columbia Montrail is a sub-brand of..." -> a sub-brand article, not the brand
      - Timberland: description says "American manufacturer", Wikidata said
        United Kingdom (a different entity with the same label) -> keep the
        description, drop the contradicted country
    """
    text = (description or "").strip()
    lowered = text.lower()

    if not text or "may refer to" in lowered[:200]:
        return "", country
    if re.search(r"\(.*\bborn\b[^)]*\)", text[:250]) or re.search(r"\bborn (january|february|march|april|may|june|july|august|september|october|november|december) \d", lowered[:250]):
        return "", ""
    if re.search(r"\bis an? sub-brand\b", lowered[:200]):
        return "", ""

    stated = re.search(r"\bis an? (?:(?:major|publicly traded|multinational|global|leading|privately held|for-profit)\s+)*([a-z]+(?: [a-z]+)?)\b", lowered[:300])
    if stated and country:
        words = stated.group(1).split()
        for candidate in (" ".join(words), words[0]):
            implied = NATIONALITY_TO_COUNTRY.get(candidate)
            if implied:
                if implied != country:
                    country = ""
                break
    return text, country


def top_brands(products_csv: Path, limit: int) -> list[str]:
    counts: Counter[str] = Counter()
    with products_csv.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            brand = (row.get("brand") or "").strip()
            if brand:
                counts[brand] += 1
    return [brand for brand, _ in counts.most_common(limit)]


def _title_matches_brand(title: str, brand: str) -> bool:
    """Guard against confidently returning the wrong company's article.

    Taking search hit #1 blindly is not good enough: searching
    "Adidas footwear company" returns the article for Five Ten Footwear (an
    Adidas subsidiary), which would attribute a subsidiary's description to the
    parent brand. Requiring the article title to actually contain the brand name
    rejects that case and leaves the field blank instead of wrong.
    """
    normalized_title = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
    normalized_brand = re.sub(r"[^a-z0-9]+", " ", brand.lower()).strip()
    if not normalized_brand:
        return False
    # Whole-token match only. Substring matching is actively dangerous here:
    # "clarks" is a substring of "clarksdale", so a substring check matched the
    # Wikidata entity for Clarksdale, Mississippi and stamped the British shoe
    # company Clarks with country_of_origin="United States".
    title_tokens = set(normalized_title.split())
    brand_tokens = normalized_brand.split()
    return all(token in title_tokens for token in brand_tokens)


_ENTITY_HINTS = {"brand", "company", "corporation", "footwear", "shoes", "shoe", "sportswear", "manufacturer"}


def _match_rank(title: str, brand: str) -> tuple[int, int, int] | None:
    """Lower is better; None means not a match at all.

    Picking the first token-matching search hit was still wrong: for Puma the
    top hit is "Puma Clyde" (a shoe line), not the company. So rank instead:
    an exact title match wins; a "(brand)"/"(company)" style disambiguator is
    a strong signal the article is about the entity itself; and every extra
    word beyond the brand name counts against the candidate.
    """
    if not _title_matches_brand(title, brand):
        return None
    lowered = title.lower()
    hint_present = any(re.search(rf"\(([^)]*\b{h}\b[^)]*)\)", lowered) for h in _ENTITY_HINTS)
    base = re.sub(r"\([^)]*\)", " ", lowered)
    base_tokens = re.sub(r"[^a-z0-9]+", " ", base).split()
    brand_tokens = re.sub(r"[^a-z0-9]+", " ", brand.lower()).split()
    extra = max(len(base_tokens) - len(brand_tokens), 0)
    exact = 0 if base_tokens == brand_tokens else 1
    return (exact, 0 if hint_present else 1, extra)


def _best_match(candidates: list, brand: str, key):
    ranked = [(rank, item) for item in candidates if (rank := _match_rank(key(item), brand)) is not None]
    if not ranked:
        return None
    ranked.sort(key=lambda pair: pair[0])
    return ranked[0][1]


def wikipedia_summary(session: requests.Session, brand: str, delay: float) -> tuple[str, str] | None:
    """Return (extract, page_url) for the best-matching Wikipedia article."""
    search = polite_get(
        session,
        WIKI_API,
        {
            "action": "query",
            "list": "search",
            "srsearch": f"{brand} shoe brand",
            "srlimit": 8,
            "format": "json",
        },
        delay,
    )
    hits = search.json().get("query", {}).get("search", [])
    best = _best_match(hits, brand, key=lambda hit: hit["title"])
    if not best:
        return None
    title = best["title"]

    detail = polite_get(
        session,
        WIKI_API,
        {
            "action": "query",
            "prop": "extracts",
            "exintro": 1,
            "explaintext": 1,
            "redirects": 1,
            "titles": title,
            "format": "json",
        },
        delay,
    )
    pages = detail.json().get("query", {}).get("pages", {})
    for page in pages.values():
        extract = (page.get("extract") or "").strip()
        if extract:
            url = "https://en.wikipedia.org/wiki/" + title.replace(" ", "_")
            return extract[:1500], url
    return None


def _labels(session: requests.Session, ids: list[str], delay: float) -> dict[str, str]:
    if not ids:
        return {}
    response = polite_get(
        session,
        WIKIDATA_API,
        {"action": "wbgetentities", "ids": "|".join(ids), "props": "labels", "languages": "en", "format": "json"},
        delay,
    )
    entities = response.json().get("entities", {})
    return {key: value.get("labels", {}).get("en", {}).get("value", "") for key, value in entities.items()}


def wikidata_facts(session: requests.Session, brand: str, delay: float) -> dict[str, str]:
    search = polite_get(
        session,
        WIKIDATA_API,
        {"action": "wbsearchentities", "search": brand, "language": "en", "limit": 5, "format": "json"},
        delay,
    )
    hits = search.json().get("search", [])
    # Same guard as the Wikipedia lookup: an unverified first hit produced
    # country_of_origin="United States" for Clarks, a British company.
    entity = _best_match(hits, brand, key=lambda hit: hit.get("label", ""))
    if not entity:
        return {}

    entity_response = polite_get(
        session,
        WIKIDATA_API,
        {"action": "wbgetentities", "ids": entity["id"], "props": "claims", "format": "json"},
        delay,
    )
    claims = entity_response.json().get("entities", {}).get(hits[0]["id"], {}).get("claims", {})

    def entity_id(prop: str) -> str | None:
        for claim in claims.get(prop, []):
            value = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
            if isinstance(value, dict) and value.get("id"):
                return value["id"]
        return None

    def text(prop: str) -> str:
        for claim in claims.get(prop, []):
            value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
            if isinstance(value, dict) and value.get("text"):
                return str(value["text"])
            if isinstance(value, str):
                return value
        return ""

    # P495 (country of origin) before P17 (country): for a company entity P17
    # is frequently the current HQ/jurisdiction rather than where the brand
    # originated, which is the field this dataset actually asks for.
    country_id = entity_id("P495") or entity_id("P17")
    parent_id = entity_id("P749")
    labels = _labels(session, [i for i in (country_id, parent_id) if i], delay)

    country = labels.get(country_id or "", "")
    country = COUNTRY_ALIASES.get(country, country)
    return {
        "country_of_origin": country if country in SUPPORTED_COUNTRIES else "",
        "parent_company": labels.get(parent_id or "", ""),
        "tagline": text("P1451"),
    }



def resanitize(path: Path) -> int:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    changed = 0
    for row in rows:
        before = (row["brand_description"], row["country_of_origin"])
        description, country = sanitize_fact(row["brand"], row["brand_description"], row["country_of_origin"])
        if not description:
            row["source_url"] = ""
        row["brand_description"], row["country_of_origin"] = description, country
        if (description, country) != before:
            changed += 1
            print(f"  cleaned {row['brand']}: description={'kept' if description else 'dropped'} country={country or '-'}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"resanitized {len(rows)} rows, {changed} changed -> {path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--top-brands", type=int, default=60, help="How many brands, by catalog product count")
    parser.add_argument("--products", type=Path, default=None)
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between API calls (Wikimedia 429s below ~1s)")
    parser.add_argument("--resanitize", action="store_true", help="Re-apply sanitize_fact() to the existing CSV without any network calls")
    args = parser.parse_args()

    if args.resanitize:
        return resanitize(Path(__file__).resolve().parents[1] / "datasets" / "product_intelligence" / "raw" / "brand_facts.csv")

    root = Path(__file__).resolve().parents[1]
    products_csv = args.products
    if products_csv is None:
        versions = root / "datasets" / "versions"
        candidates = [p for p in versions.glob("catalog_v*") if p.is_dir() and p.name.removeprefix("catalog_v").isdigit()]
        if not candidates:
            raise SystemExit("No catalog version found; run the catalog build first.")
        products_csv = max(candidates, key=lambda p: int(p.name.removeprefix("catalog_v"))) / "products.csv"

    brands = top_brands(products_csv, args.top_brands)
    print(f"fetching brand facts for {len(brands)} brands")

    out_path = root / "datasets" / "product_intelligence" / "raw" / "brand_facts.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    collected_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    written = with_description = 0
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for index, brand in enumerate(brands, start=1):
            description = url = ""
            facts: dict[str, str] = {}
            try:
                summary = wikipedia_summary(session, brand, args.delay)
                if summary:
                    description, url = summary
                time.sleep(args.delay)
                facts = wikidata_facts(session, brand, args.delay)
                time.sleep(args.delay)
            except requests.RequestException as error:
                print(f"  [warn] {brand}: {error}")

            description, country = sanitize_fact(brand, description, facts.get("country_of_origin", ""))
            if not description:
                url = ""
            writer.writerow(
                {
                    "intelligence_record_id": f"wiki-{index:04d}",
                    "brand": brand,
                    "source": "wikipedia",
                    "source_url": url,
                    "brand_description": description,
                    "tagline": facts.get("tagline", ""),
                    "parent_company": facts.get("parent_company", ""),
                    "country_of_origin": country,
                    "collected_at": collected_at,
                }
            )
            written += 1
            if description:
                with_description += 1
            if index % 10 == 0:
                print(f"  {index}/{len(brands)} brands", flush=True)

    print(f"brands written: {written} ({with_description} with a Wikipedia description) -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
