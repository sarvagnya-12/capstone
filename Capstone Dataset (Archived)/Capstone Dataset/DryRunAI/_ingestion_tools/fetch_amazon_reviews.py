"""Stream Amazon Reviews 2023 footwear data out of Hugging Face.

The source files are enormous -- meta_Clothing_Shoes_and_Jewelry.jsonl is ~18GB
and Clothing_Shoes_and_Jewelry.jsonl is ~28GB, against ~47GB of free disk. They
are therefore streamed over HTTPS and filtered line by line; neither file is
ever written to disk in full. Only the filtered footwear subset is kept.

Two passes:
  1. Metadata -> keep footwear products (see footwear_filter.py), up to --meta-cap.
     Produces the ASIN set that pass 2 filters against, plus the price/title/image
     data that Stage 1 (catalog) and Stage 4 (market) consume.
  2. Reviews  -> keep reviews whose parent_asin is in that set, up to --review-cap.

Field names are renamed here rather than in the pipeline's collectors: HF's 2023
schema uses `user_id`/`timestamp`/`helpful_vote`, while AmazonReviewCollector's
FIELD_ALIASES expect `reviewername`/`review_date`/`helpful_votes`. Renaming at the
edge keeps the frozen collector untouched. HF reviews carry no review ID at all,
so a deterministic one is synthesized from (asin, user_id, timestamp).

LICENSE NOTE: Amazon Reviews 2023 (McAuley Lab, UCSD) publishes no explicit
license grant. It is a widely used academic research dataset and this is an
academic capstone, but that ambiguity is real and is recorded here rather than
glossed over.

Usage:
    python _ingestion_tools/fetch_amazon_reviews.py
    python _ingestion_tools/fetch_amazon_reviews.py --review-cap 500000 --meta-cap 300000
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent))
from footwear_filter import classify  # noqa: E402

REPO = "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main"
META_URL = f"{REPO}/raw/meta_categories/meta_Clothing_Shoes_and_Jewelry.jsonl"
REVIEW_URL = f"{REPO}/raw/review_categories/Clothing_Shoes_and_Jewelry.jsonl"

SAMPLE_LIMIT = 15


def stream_jsonl(url: str, description: str):
    """Yield parsed JSON objects from a remote .jsonl without buffering the file."""
    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        bar = tqdm(unit="line", desc=description, mininterval=2.0)
        try:
            for raw in response.iter_lines(chunk_size=1 << 20, decode_unicode=True):
                if not raw:
                    continue
                bar.update(1)
                try:
                    yield json.loads(raw)
                except json.JSONDecodeError:
                    continue
        finally:
            bar.close()


def collect_footwear_metadata(meta_cap: int, scan_cap: int) -> tuple[dict, dict]:
    """Pass 1: stream product metadata, keep footwear rows."""
    kept: dict[str, dict] = {}
    reasons: Counter = Counter()
    samples: dict[str, list[str]] = {"kept": [], "rejected": []}
    scanned = 0

    for record in stream_jsonl(META_URL, "meta scan"):
        scanned += 1
        decision = classify(record)
        reasons[decision.reason] += 1

        if decision.keep:
            asin = record.get("parent_asin")
            if asin and asin not in kept:
                kept[asin] = record
                if len(samples["kept"]) < SAMPLE_LIMIT:
                    samples["kept"].append(f"[{decision.reason}] {record.get('title', '')[:110]}")
        elif len(samples["rejected"]) < SAMPLE_LIMIT:
            samples["rejected"].append(f"[{decision.reason}] {record.get('title', '')[:110]}")

        if len(kept) >= meta_cap or scanned >= scan_cap:
            break

    stats = {
        "scanned": scanned,
        "kept": len(kept),
        "reasons": dict(reasons.most_common()),
        "samples": samples,
        "stopped_because": "meta_cap" if len(kept) >= meta_cap else "scan_cap_or_eof",
    }
    return kept, stats


def _iso_date(timestamp) -> str | None:
    """HF timestamps are unix epoch milliseconds."""
    try:
        return datetime.fromtimestamp(int(timestamp) / 1000, tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def _synth_review_id(record: dict) -> str:
    seed = f"{record.get('asin')}|{record.get('user_id')}|{record.get('timestamp')}|{record.get('title')}"
    return "amz-" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:20]


def collect_reviews(asins: set[str], review_cap: int, scan_cap: int, out_path: Path) -> dict:
    """Pass 2: stream reviews, keep those for known footwear products."""
    kept = 0
    scanned = 0
    matched_asins: set[str] = set()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as handle:
        for record in stream_jsonl(REVIEW_URL, "review scan"):
            scanned += 1
            asin = record.get("parent_asin") or record.get("asin")
            if asin not in asins:
                if scanned >= scan_cap:
                    break
                continue

            handle.write(
                json.dumps(
                    {
                        "review_id": _synth_review_id(record),
                        "asin": record.get("asin"),
                        "parent_asin": asin,
                        "title": record.get("title"),
                        "text": record.get("text"),
                        "rating": record.get("rating"),
                        "review_date": _iso_date(record.get("timestamp")),
                        "reviewer_name": record.get("user_id"),
                        "verified_purchase": record.get("verified_purchase"),
                        "helpful_votes": record.get("helpful_vote"),
                        "language": "en",
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            kept += 1
            matched_asins.add(asin)

            if kept >= review_cap or scanned >= scan_cap:
                break

    return {
        "scanned": scanned,
        "kept": kept,
        "distinct_products_with_reviews": len(matched_asins),
        "stopped_because": "review_cap" if kept >= review_cap else "scan_cap_or_eof",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--meta-cap", type=int, default=300_000, help="Max footwear products to keep (default: 300000)")
    parser.add_argument("--review-cap", type=int, default=500_000, help="Max reviews to keep (default: 500000)")
    parser.add_argument("--max-meta-scan", type=int, default=4_000_000, help="Safety limit on metadata lines scanned")
    parser.add_argument("--max-review-scan", type=int, default=25_000_000, help="Safety limit on review lines scanned")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    meta_out = root / "datasets" / "raw" / "amazon" / "amazon_meta_footwear.jsonl"
    review_out = root / "datasets" / "reviews" / "raw" / "amazon_reviews.jsonl"
    report_out = root / "datasets" / "raw" / "amazon" / "acquisition_report.json"

    print("=== Pass 1/2: footwear metadata ===")
    metadata, meta_stats = collect_footwear_metadata(args.meta_cap, args.max_meta_scan)
    meta_out.parent.mkdir(parents=True, exist_ok=True)
    with meta_out.open("w", encoding="utf-8") as handle:
        for record in metadata.values():
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"  scanned {meta_stats['scanned']:,} -> kept {meta_stats['kept']:,} footwear products")

    print("\n=== Pass 2/2: reviews for those products ===")
    review_stats = collect_reviews(set(metadata), args.review_cap, args.max_review_scan, review_out)
    print(f"  scanned {review_stats['scanned']:,} -> kept {review_stats['kept']:,} reviews")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {"metadata": META_URL, "reviews": REVIEW_URL},
        "license_note": "Amazon Reviews 2023 (McAuley Lab, UCSD) publishes no explicit license grant; used here for academic capstone research.",
        "filter_note": "Footwear isolation is heuristic (category path, then title keywords, minus an exclusion list). No ground-truth footwear label exists in the source data.",
        "metadata_pass": meta_stats,
        "review_pass": review_stats,
        "outputs": {"metadata": str(meta_out), "reviews": str(review_out)},
    }
    report_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nReport: {report_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
