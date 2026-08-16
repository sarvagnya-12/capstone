# DryRunAI Service 04: Market Service

The Market Service collects factual market records for products. It never estimates, predicts, or infers missing values, and it never modifies `products.csv`.

## Folder Structure

```text
04_market_service/
  market_service/
    collectors/    Plugin market collectors.
    processors/    Product linking and field normalization.
    validators/    Record validation and duplicate detection.
    exporters/     Versioned market, quarantine, metadata, and report exports.
    reports/       Report payload builders.
    config/        Service defaults.
  logs/            Service-local placeholder. Runtime logs default to datasets/processed/logs.
  tests/           Unit tests.
  docs/            Additional service documentation.
  output/          Service-local placeholder.
```

## Collector Framework

All Market collectors inherit the shared `BaseCollector` through `BaseMarketCollector`. Collector plugins register when their modules are discovered through the shared collector registry.

Configured plugin modules live in:

```text
04_market_service/market_service/config/default_config.json
```

The service creates collectors through `shared.collectors.CollectorFactory`.

## Supported Collectors

Official: Nike, Adidas, Puma, New Balance, ASICS

Retail: Zappos, Foot Locker, JD Sports

Marketplace: StockX, GOAT

## Outputs

```text
datasets/market/versions/market_v1/processed/market.csv
datasets/market/processed/market_v1/market.csv
datasets/market/quarantine/market_v1/rejected_market.csv
datasets/market/quarantine/market_v1/duplicate_market.csv
datasets/market/reports/market_v1/market_summary.json
datasets/market/reports/market_v1/statistics.json
datasets/market/reports/market_v1/validation_report.json
datasets/market/reports/market_v1/duplicate_report.json
datasets/market/metadata/market_v1/source_metadata.json
```

Versions are never overwritten.

## Run

From the DryRunAI root:

```powershell
$env:PYTHONPATH = ".;04_market_service"
python -m market_service --sources nike,zappos,stockx --market "datasets/market/raw/sample_market.csv" --products "datasets/versions/catalog_v1/products.csv"
```

## Adding a Market Collector

1. Add a collector class under `market_service/collectors/`.
2. Inherit `BaseMarketCollector`.
3. Set `source_name`, `market_type`, and `default_price_type`.
4. Add the module to `collector_plugins` in config if it lives in a new module.
5. Add the source name to `supported_collectors`.

Collectors should only collect factual source records. Normalization, validation, duplicate detection, export, and reports remain service responsibilities.

