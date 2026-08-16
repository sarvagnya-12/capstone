# DryRunAI Service 05: Product Intelligence Service

The Product Intelligence Service collects structured factual business intelligence about products and brands. It does not perform AI, sentiment analysis, inference, prediction, or rewriting.

## Folder Structure

```text
05_product_intelligence_service/
  product_intelligence_service/
    collectors/    Plugin collectors for brand and public intelligence sources.
    processors/    Product linking and field normalization.
    validators/    Required field, URL, country, region, and duplicate validation.
    exporters/     Versioned exports, quarantine, metadata, and reports.
    reports/       Report payload builders.
    config/        Service defaults.
  logs/            Service-local placeholder. Runtime logs default to datasets/processed/logs.
  tests/           Unit tests.
  docs/            Additional service documentation.
  output/          Service-local placeholder.
```

## Collector Framework

Collectors inherit the shared `BaseCollector` through `BaseIntelligenceCollector`. Plugin modules are listed in config and discovered through the shared collector registry. The service creates collectors with `CollectorFactory`.

## How Product Intelligence Works

1. Read `products.csv` from Service 01.
2. Collect factual rows from configured source files.
3. Link rows to DryRunAI Product IDs.
4. Normalize controlled fields such as regions, countries, gender, lifestyle, and strategy names.
5. Preserve descriptions and other factual wording.
6. Validate records.
7. Export accepted rows, quarantine rejected/duplicate rows, and generate reports.

## Outputs

```text
datasets/product_intelligence/versions/product_intelligence_v1/processed/product_intelligence.csv
datasets/product_intelligence/processed/product_intelligence_v1/product_intelligence.csv
datasets/product_intelligence/quarantine/product_intelligence_v1/rejected_product_intelligence.csv
datasets/product_intelligence/quarantine/product_intelligence_v1/duplicate_product_intelligence.csv
datasets/product_intelligence/reports/product_intelligence_v1/product_intelligence_summary.json
datasets/product_intelligence/reports/product_intelligence_v1/validation_report.json
datasets/product_intelligence/reports/product_intelligence_v1/duplicate_report.json
datasets/product_intelligence/reports/product_intelligence_v1/statistics.json
```

## Run

From the DryRunAI root:

```powershell
$env:PYTHONPATH = ".;05_product_intelligence_service"
python -m product_intelligence_service --sources nike,wikipedia,wikidata --intelligence "datasets/product_intelligence/raw/sample_product_intelligence.csv" --products "datasets/versions/catalog_v1/products.csv"
```

## Adding a Brand Collector

1. Add a collector class under `product_intelligence_service/collectors/`.
2. Inherit `BaseIntelligenceCollector`.
3. Set `source_name`.
4. Add the module to `collector_plugins` if needed.
5. Add the source to `supported_collectors`.

Collectors only collect factual source rows. They must not infer marketing strategy, audience, positioning, or missing values.

## Future AI Consumption

Future AI services should consume `product_intelligence.csv` as structured factual context. They should treat this service output as collected evidence, not model-generated insight.

