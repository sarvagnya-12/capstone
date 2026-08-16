# DryRunAI

DryRunAI is organized as a multi-stage dataset system. Script 1, the Product Catalog Builder, now lives under `01_catalog_builder/` and uses shared project-level schemas, taxonomy, and datasets.

No GAN, LLM, or API code is included in Script 1.

## Project Layout

```text
DryRunAI/
  schemas/                    Global dataset contracts read by all builders.
  taxonomy/                   Shared controlled vocabularies and synonyms.
  datasets/
    raw/                      Source datasets.
    normalized/               Normalized intermediate outputs.
    merged/                   Merged intermediate outputs.
    processed/                Reports, logs, registries, and other processed artifacts.
    versions/                 Versioned final catalog outputs.
    assets/                   Versioned product assets managed by Service 02.
    quarantine/               Invalid or duplicate asset files retained for audit.
  shared/                     Reusable constants, config, IO, validation, logging, utils, and exceptions.
  01_catalog_builder/         Script 1: Product Catalog Builder.
  02_asset_manager/           Service 02: Asset Manager.
  03_review_builder/          Service 03: Review Builder.
  04_market_service/          Service 04: Market Service.
  05_product_intelligence_service/  Service 05: Product Intelligence Service.
  06_knowledge_integration_service/  Service 06: Knowledge Integration Service.
  07_dataset_quality_service/  Service 07: Dataset Quality Service.
```

## Global Schemas

Schemas are global because no individual builder owns the shape of shared DryRunAI datasets. Future scripts must read schema files from `schemas/` and must not infer, reorder, remove, rename, or append columns in shared outputs.

The product catalog contract lives only at:

```text
schemas/products_schema.json
```

`products.csv` must follow that schema. Any product schema change requires an intentional schema version update.

## Global Taxonomy

Taxonomy is global because builders need consistent names for brands, categories, colors, materials, genders, image types, strategies, lifestyles, stopwords, and synonyms.

All builders should read taxonomy from:

```text
taxonomy/
```

No builder should maintain private copies of taxonomy files.

## Catalog Builder

Script 1 builds the DryRunAI Master Sneaker Catalog. It reads source product data, normalizes fields through shared taxonomy, validates required product attributes, detects duplicates, assigns permanent product IDs, writes versioned catalog outputs, and generates structured reports.

Run from the DryRunAI root:

```powershell
$env:PYTHONPATH = ".;01_catalog_builder"
python -m catalog_builder --source zappos --input "datasets/raw/zappos50k.csv"
```

Because the package lives under `01_catalog_builder/`, either run from that directory or set `PYTHONPATH` when running from the project root:

```powershell
$env:PYTHONPATH = ".;01_catalog_builder"
python -m catalog_builder --source zappos --input "datasets/raw/zappos50k.csv"
```

Each run creates a new catalog version:

```text
datasets/versions/catalog_v1/products.csv
datasets/processed/reports/catalog_v1/catalog_summary.json
datasets/processed/reports/catalog_v1/validation_report.json
datasets/processed/reports/catalog_v1/duplicate_report.json
datasets/processed/reports/catalog_v1/statistics.json
```

The pipeline never overwrites prior catalog versions. Product IDs are stored in `datasets/processed/id_registry.json` and are never reused.

## Product Columns

The current canonical `products.csv` columns are:

```text
product_id, brand, model, category, subcategory, gender, retail_price,
release_year, primary_color, secondary_color, material, source_url, source,
source_product_id, confidence, status
```

`source_url` is a required schema column. Its value may be blank because some source datasets do not provide product pages. When supplied, it is validated as an HTTP or HTTPS URL.

## Adding Future Builders

Future builders should follow the same rule: read shared schemas from `schemas/`, read shared taxonomy from `taxonomy/`, and write intermediate or final datasets under `datasets/`.

Builders may own their code and local configuration, but they must not own global schemas or taxonomy.

All services should use the shared infrastructure package in `shared/` for configuration loading, project-root path handling, structured rotating logging, common IO, validation helpers, hashing, project exceptions, and collector discovery.

The shared collector framework lives in `shared/collectors/`. New collectors should inherit `BaseCollector`, register through plugin discovery, and be created with `CollectorFactory`.

## Asset Manager

Service 02 reads the frozen product catalog and manages product assets. Phase 1 supports images.

```powershell
$env:PYTHONPATH = ".;02_asset_manager"
python -m asset_manager --products "datasets/versions/catalog_v1/products.csv"
```

If `--products` is omitted, Service 02 reads the latest `datasets/versions/catalog_v*/products.csv`. It never modifies `products.csv`.

## Review Builder

Service 03 reads the frozen product catalog and builds product review datasets. It preserves original review text and does not perform AI tasks, sentiment analysis, spam detection, or trust scoring.

```powershell
$env:PYTHONPATH = ".;03_review_builder"
python -m review_builder --source amazon --reviews "datasets/reviews/raw/amazon_reviews.jsonl" --products "datasets/versions/catalog_v1/products.csv"
```

If `--products` is omitted, Service 03 reads the latest `datasets/versions/catalog_v*/products.csv`. It never modifies `products.csv`.

## Market Service

Service 04 reads the frozen product catalog and builds factual market datasets. It never estimates, predicts, infers missing values, or merges prices.

```powershell
$env:PYTHONPATH = ".;04_market_service"
python -m market_service --sources nike,zappos,stockx --market "datasets/market/raw/sample_market.csv" --products "datasets/versions/catalog_v1/products.csv"
```

If `--products` is omitted, Service 04 reads the latest `datasets/versions/catalog_v*/products.csv`. It never modifies `products.csv`.

## Product Intelligence Service

Service 05 reads the frozen product catalog and collects factual product and brand intelligence. It does not perform AI, inference, prediction, sentiment analysis, or rewriting.

```powershell
$env:PYTHONPATH = ".;05_product_intelligence_service"
python -m product_intelligence_service --sources nike,wikipedia,wikidata --intelligence "datasets/product_intelligence/raw/sample_product_intelligence.csv" --products "datasets/versions/catalog_v1/products.csv"
```

If `--products` is omitted, Service 05 reads the latest `datasets/versions/catalog_v*/products.csv`. It never modifies `products.csv`.

## Knowledge Integration Service

Service 06 integrates products, image metadata, reviews, market records, and product intelligence into the unified Master Dataset. It does not collect new data, modify source datasets, infer missing values, summarize, or run AI.

```powershell
$env:PYTHONPATH = ".;06_knowledge_integration_service"
python -m knowledge_integration_service
```

It exports `master_products.csv`, `master_products.parquet`, `master_products.jsonl`, and relationship/validation reports under `datasets/master/`.

## Dataset Quality Service

Service 07 validates outputs from Services 01-06 and generates quality reports. It does not collect data and does not modify datasets.

```powershell
$env:PYTHONPATH = ".;07_dataset_quality_service"
python -m dataset_quality_service
```

It exports `validation_report.json`, `dataset_health.json`, `missing_data_report.json`, `relationship_report.json`, and `statistics.json` under `datasets/quality/reports/`.

## Adding a Catalog Collector

1. Create `01_catalog_builder/catalog_builder/collectors/<source>/collector.py`.
2. Subclass `BaseCollector`.
3. Set `source_name`.
4. Implement `collect(input_path: Path) -> list[RawProduct]`.
5. Register it in `build_registry()` inside `01_catalog_builder/catalog_builder/pipeline.py`.

Collectors should only read source data and map it to `RawProduct`. Normalization, validation, matching, ID assignment, and export remain shared pipeline responsibilities.
