# DryRunAI Service 06: Knowledge Integration Service

The Knowledge Integration Service integrates outputs from Services 01-05 into one unified Master Dataset. It does not collect new data, modify source datasets, infer missing values, summarize content, perform feature engineering, or run AI.

## Folder Structure

```text
06_knowledge_integration_service/
  knowledge_integration_service/
    collectors/    Readers for previous service outputs.
    processors/    Master product integration and relationship construction.
    validators/    Referential integrity and schema validation.
    exporters/     CSV, Parquet, JSONL, quarantine, and reports.
    reports/       Merge, relationship, statistics, and validation report builders.
    config/        Service defaults.
  logs/            Service-local placeholder. Runtime logs default to datasets/processed/logs.
  tests/           Unit and integration-style tests.
  docs/            Additional service documentation.
  output/          Service-local placeholder.
```

## Merge Strategy

Each Catalog Service Product ID becomes exactly one Master Product. Child datasets are not duplicated into standalone rows. The master row stores references to related images, reviews, market records, and product intelligence records.

## Relationship Model

Relationships are represented through Product IDs and reference arrays:

- Product -> Images
- Product -> Reviews
- Product -> Market Records
- Product -> Product Intelligence

No graph database is used.

## Export Formats

The service writes:

```text
datasets/master/master_products.csv
datasets/master/master_products.parquet
datasets/master/master_products.jsonl
datasets/master/master_v1/
```

CSV is human-readable. Parquet is optimized for ML workflows. JSONL is suitable for retrieval and downstream LLM-oriented pipelines.

## Downstream AI Consumption

Future AI systems should consume `master_products.jsonl` or `master_products.parquet` as structured factual context. Provenance is preserved so downstream systems can trace every relationship back to source datasets and source URLs.

## Run

From the DryRunAI root:

```powershell
$env:PYTHONPATH = ".;06_knowledge_integration_service"
python -m knowledge_integration_service
```

Explicit paths can be supplied with `--products`, `--images`, `--reviews`, `--market`, and `--product-intelligence`.

