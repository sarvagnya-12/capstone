# Dataset Pipeline Population — Progress & Resume Point

**Last updated:** 2026-09-19 — **ALL STEPS 13a–13h COMPLETE.** Data is in Postgres.
**Goal:** Populate the 7-stage ETL pipeline with real data, then ingest into the core app's `ref_*` Postgres tables (IMPLEMENTATION.md Step 13).
**Plan file:** `C:\Users\ADMIN\.claude\plans\you-are-a-senior-synthetic-starlight.md`

---

## Environment

```bash
cd "G:/Capstone/Capstone Dataset (Archived)/Capstone Dataset/DryRunAI"
# Dedicated venv (system Python has a broken `datasets` namespace package — do not use it)
./.venv/Scripts/python.exe
```

Each pipeline stage needs its own PYTHONPATH, e.g.:
```bash
PYTHONPATH=".;02_asset_manager" ./.venv/Scripts/python.exe -m asset_manager --products ...
```

---

## Status: 13a–13h ALL DONE

| Step | What | Status |
|---|---|---|
| 13a | Acquisition (Zappos + Amazon + Wikipedia) | ✅ Done |
| 13b | Conversion to collector-ready CSVs | ✅ Done |
| 13c | Stage 1 multi-source catalog build | ✅ Done — 109,808 unique products |
| 13d | Stage 2 image processing | ✅ Done — 46,269 images |
| 13e | Stage 3 (reviews) + Stage 4 (market) | ✅ Done — 496,592 reviews, 36,096 prices |
| 13f | Stage 5 (product intelligence) | ✅ Done — 41,945 rows, 60 brands |
| 13g | Stage 6 (merge) + Stage 7 (quality) | ✅ Done — 109,808 master products, 0 broken refs |
| 13h | Ingest into Postgres `ref_*` tables | ✅ Done — 730,713 rows, verified |

### What exists on disk right now

| Artifact | Count | Path |
|---|---|---|
| Zappos images (raw) | 50,025 | `datasets/raw/zappos/ut-zap50k-images/` |
| Zappos catalog CSV | 24,522 | `datasets/raw/zappos/zappos_utzap50k.csv` |
| Zappos image manifest | 50,025 | `datasets/raw/zappos/zappos_image_manifest.csv` |
| Amazon footwear metadata | 300,000 | `datasets/raw/amazon/amazon_meta_footwear.jsonl` |
| Amazon reviews (real text) | 500,000 | `datasets/reviews/raw/amazon_reviews.jsonl` |
| Amazon catalog CSV | 90,402 | `datasets/raw/amazon/amazon_catalog.csv` |
| Amazon market/price rows | 36,928 | `datasets/market/raw/amazon_market.csv` |
| **Built catalog** | **109,808** | `datasets/versions/catalog_v1/products.csv` (114,683 before same-fingerprint collapse) |
| Catalog + image columns | 114,683 | `datasets/versions/catalog_v1/products_with_images.csv` |
| **Stored images** | **46,269** | `datasets/assets/catalog_v1/` |
| Image metadata | 46,272 | `datasets/processed/catalog_v1/image_metadata.csv` |
| Brand facts (verified) | 60 | `datasets/product_intelligence/raw/brand_facts.csv` |
| Reviews (Stage 3 out) | 496,592 | `datasets/reviews/processed/reviews_v1/reviews.csv` |
| Market (Stage 4 out) | 36,096 | `datasets/market/processed/market_v1/market.csv` |
| Product intelligence (Stage 5 out) | 41,945 | `datasets/product_intelligence/processed/product_intelligence_v1/product_intelligence.csv` |
| **Master dataset** | **109,808** | `datasets/master/master_products.{csv,parquet,jsonl}` |
| Quality reports | — | `datasets/quality/reports/` |
| **Postgres `ref_*` tables** | **730,713** | verified: counts match CSVs, 0 orphans, 0 column drift |

Catalog composition: 24,522 Zappos + 85,286 Amazon (after collapsing 4,875 same-fingerprint listings — see bugs below); 186 cross-source fuzzy matches; 241 Amazon rows rejected (161 missing model, 83 missing brand). Zero Zappos rejections. The original 114,683-row file is kept as `products.with_duplicate_ids.csv`.

---

## Stage 7 quality score — read this before quoting the number

`project_manifest.json` now says `dataset_health_score: 17`, and five of six per-dataset scores are a flat **0**. **That number is a scorer artifact, not a data-quality verdict.** `QualityScorer.dataset_score()` subtracts a *fixed penalty per row* (2 points per product lacking a relationship, 3 per missing required field) with no normalization and a floor of 0 — it was only ever exercised on 4-row fixtures. 24,534 Zappos products with no Amazon review = −49,068 points. Any real-scale dataset scores 0 under it.

What the underlying reports actually show (`datasets/quality/reports/validation_report.json`):

| dataset | rows | duplicate IDs | broken refs | schema violations | missing required |
|---|---|---|---|---|---|
| products | 109,808 | 0 | 0 | 0 | `source_url` × 24,522 (UT-Zappos50K has no product URLs — inherent to the source) |
| images | 46,272 | 0 | 0 | 0 | — |
| reviews | 496,592 | 0 | 0 | 0 | — |
| market | 36,096 | 0 | 0 | 0 | — |
| product_intelligence | 41,945 | 0 | 0 | 0 | — |
| master | 109,808 | 0 | 0 | 0 | — |

Missing relationships are the predicted, honest non-overlap between sources: 85,286 products without images (all Amazon — Amazon contributes no images by design), 24,534 without reviews (≈ the 24,522 Zappos products), 73,712 without market data, 67,863 without brand intelligence (only the top 60 of 7,360 brands were fetched; that covers ~39% of products).

If a headline number is ever needed, quote the integrity table above, not the 17.

---

## What the core app now has

All five `ref_*` tables in Postgres are populated and verified (`scripts/ingest_dataset_pipeline.py`, run with the four `--overrides` because Stage 6 only writes `master_products.csv` into `datasets/master/`):

| table | rows |
|---|---|
| ref_products | 109,808 |
| ref_images | 46,272 |
| ref_reviews | 496,592 |
| ref_market | 36,096 |
| ref_product_intelligence | 41,945 |

24,522 products have ≥1 image (all Zappos, uniform white-background catalog photography — the GAN fine-tuning corpus). 85,274 products have ≥1 real review.

**This unblocks:** IMPLEMENTATION.md Step 14 (persona seed extraction can now draw on real `ref_product_intelligence` / `ref_reviews`), Step 17 (GAN fine-tuning on 46K real shoe images), and Phase 17 Step 44 (RAG over 496K real reviews).

---

## Key design decisions (do not silently undo these)

1. **Zappos is NOT fuzzy-matched against itself.** UT-Zappos50K has no product names, so model strings are built from subcategory + numeric ProductID. Two genuinely different Bostonian oxfords score **0.97** — above the 0.92 merge threshold. Verified directly. Zappos is deduplicated deterministically on its authoritative ProductID instead.
2. **Amazon is NOT fuzzy-matched against itself either.** Doing so was projected at ~10 hours (quadratic within brand buckets). It is matched only against Zappos. Exact-fingerprint duplicates within Amazon (same brand|model|category|gender under different ASINs) ARE collapsed — that is a dict lookup, not fuzzy matching, and skipping it produced duplicate product IDs (see bugs).
3. **Brand-bucketed comparison is provably outcome-identical**, not a shortcut: brand contributes 0.28, so differing-brand pairs cap at 0.72 — below the 0.78 threshold.
4. **Amazon contributes no images.** Zappos supplies the image corpus (uniform white-background catalog photography, far better for GAN training than inconsistent marketplace photos), and fetching 90K images over HTTP sequentially was not viable.
5. **Unmatched rows are left blank, never fabricated.** The stage validators already quarantine `missing_product_id`, which is exactly the desired honest behavior.
6. **`taxonomy/brands.json` was deliberately NOT extended.** An earlier analysis claiming ~92% of products would be rejected was **wrong** — `canonical_brand()` title-cases unknown brands rather than dropping them (verified empirically). No change was needed.

## Bugs found and fixed this session

- **Footwear filter matched 0 products** — every Amazon category path starts with the literal root `"Clothing, Shoes & Jewelry"`, so a substring check for "jewelry" rejected everything including boots. Fixed by matching taxonomy path *segments*.
- **Placeholder product IDs** — catalog CSVs used column header `source_product_id`, which matches none of `ZapposCollector.FIELD_ALIASES` (`id`/`product_id`/`asin`/`sku`/...), so every row silently got `zappos-row-N` instead of its real ProductID/ASIN. Would have broken every downstream join. Fixed to `id`; verified 0 placeholders remain.
- **`ProductIdRegistry` quadratic disk I/O** — rewrites its entire JSON file on every new product. Worked around with a deferred-save subclass in the driver (frozen file untouched).
- **Wikipedia 429 rate limiting** — added backoff honoring `Retry-After`.
- **Wrong Wikipedia/Wikidata entities** — "Adidas footwear company" returned the *Five Ten* subsidiary; "Clarks" returned *Clarksdale, Mississippi*; "Puma" returned the *Puma Clyde* shoe line; "Jessica Simpson"/"Stuart Weitzman" returned the *people*; "Columbia" returned a sub-brand; Timberland got `United Kingdom` from a same-label Wikidata entity. Fixed with whole-token matching, a ranked best-match (exact title > `(brand)` disambiguator > fewest extra words), and a text-driven `sanitize_fact()` that blanks contradicted values (blank beats wrong). `--resanitize` re-applies it offline.
- **Invisible regex corruption** — patching the script through a bash heredoc turned `\b` into literal backspace characters (`^H`), so three sanitization regexes could never match and silently did nothing. Found with `cat -A`; fixed by rewriting the bytes. Lesson: verify a patched regex fires on a known-positive input, not just that the file "looks right".
- **Duplicate product IDs in the catalog** — the ID registry hands out one ID per exact fingerprint (brand|model|category|gender), so Amazon listings of the same shoe under different ASINs (colourways/sizes) all received the same ID, and because Amazon-vs-Amazon fuzzy matching was (correctly) off, none were merged: 3,334 IDs appeared more than once, 4,875 extra rows. Collapsed to 109,808 unique products (keep-first), and the driver now dedups by exact fingerprint within a source so a rebuild is clean. Stages 4–5 had already been silently deduping to the same 109,808.
- **CSV field-size limit (twice)** — `master_products.csv`'s JSON reference arrays exceed Python's 128 KB default field limit at real scale. Stage 7's frozen shared reader crashed; wrapped via `_ingestion_tools/run_dataset_quality_service.py`. The core app's `scripts/ingest_dataset_pipeline.py` had the same bug; fixed in place.
- **Postgres 65,535-parameter limit** — `ingest_dataset_pipeline.py` sent one INSERT with every row bound as parameters (36,096 rows × 16 cols ≈ 577K). Fixed by batching upserts by column count.

## Not committed

Nothing from this work is committed yet. `.gitignore` was extended so the acquired raw data (hundreds of MB) and pipeline outputs stay out; what git sees is: the new `_ingestion_tools/` scripts, the two additive `amazon` collectors, `requirements.txt`, `brand_facts.csv` (60 rows), the fixed `scripts/ingest_dataset_pipeline.py`, `.gitignore`, and the updated `project_manifest.json`.
