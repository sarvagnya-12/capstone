# DryRunAI Service 02: Asset Manager

The Asset Manager manages assets associated with products produced by Script 1. Phase 1 supports images, while the structure is prepared for future asset families such as videos, packaging, logos, advertisements, 3D models, and PDF manuals.

The service reads `products.csv` and `schemas/products_schema.json`. It never modifies `products.csv`.

## Folder Structure

```text
02_asset_manager/
  asset_manager/
    collectors/    Product catalog and asset reference readers.
    processors/    Download, hash, deduplicate, and store assets.
    validators/    Image validation.
    exporters/     Metadata, reports, and versioned outputs.
    reports/       Report payload builders.
    config/        Service defaults.
  logs/            Service-local placeholder. Runtime logs default to datasets/processed/logs.
  tests/           Unit tests for critical modules.
  docs/            Additional service documentation.
  output/          Service-local placeholder. Runtime outputs default to datasets/.
```

## Outputs

Versioned outputs are written under `datasets/`:

```text
datasets/assets/catalog_v1/DRY-SNK-000001/images/IMG-000001.jpg
datasets/assets/catalog_v1/DRY-SNK-000001/metadata.json
datasets/processed/catalog_v1/image_metadata.csv
datasets/processed/catalog_v1/asset_summary.json
datasets/processed/catalog_v1/validation_report.json
datasets/processed/catalog_v1/download_report.json
datasets/processed/catalog_v1/duplicate_report.json
datasets/quarantine/catalog_v1/
```

Versions are never overwritten.

## Image Metadata

`image_metadata.csv` stores image ID, product ID, source, source URL, original image URL, image type, width, height, aspect ratio, file size, SHA256, image format, download timestamp, status, and original filename.

Future services should consume `datasets/processed/catalog_v*/image_metadata.csv` instead of scanning asset folders directly.

## Validation

The service rejects corrupted images, unsupported formats, duplicate SHA256 hashes, zero-byte files, and unreadable images. Rejected files are moved to `datasets/quarantine/catalog_v*/` and are never deleted.

## Configuration

Defaults live in:

```text
02_asset_manager/asset_manager/config/default_config.json
```

Image URL columns, image type columns, formats, retries, timeouts, logging, and output paths are configurable. Shared taxonomy for image types lives in `taxonomy/image_types.json`.

## Run

From the DryRunAI root:

```powershell
$env:PYTHONPATH = ".;02_asset_manager"
python -m asset_manager --products "datasets/versions/catalog_v1/products.csv"
```

If `--products` is omitted, the service uses the latest `datasets/versions/catalog_v*/products.csv`.

## Adding Future Asset Types

Add new collectors, processors, validators, exporters, and report builders under the same service folders. Keep shared infrastructure in `shared/`, keep global schemas in `schemas/`, and keep controlled vocabularies in `taxonomy/`.

