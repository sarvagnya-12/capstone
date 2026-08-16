# DryRunAI Service 07: Dataset Quality Service

The Dataset Quality Service validates outputs from Services 01-06. It does not collect data and does not modify datasets. It only validates, scores, reports, and updates project manifest quality metadata.

## Validation Pipeline

1. Load configured dataset outputs.
2. Validate each dataset against its shared schema.
3. Check required fields, missing values, duplicate IDs, and broken Product IDs.
4. Check missing relationships across product-linked datasets.
5. Validate manifest and taxonomy consistency.
6. Generate quality scores and reports.

## Quality Metrics

The service produces per-dataset scores for:

- Product Quality
- Asset Quality
- Review Quality
- Market Quality
- Product Intelligence Quality
- Master Dataset Quality

The overall score is the average of those dataset scores. Penalties are configurable in `dataset_quality_service/config/default_config.json`.

## Outputs

Reports are written to:

```text
datasets/quality/reports/
```

Generated reports:

- `validation_report.json`
- `dataset_health.json`
- `missing_data_report.json`
- `relationship_report.json`
- `statistics.json`

## Run

From the DryRunAI root:

```powershell
$env:PYTHONPATH = ".;07_dataset_quality_service"
python -m dataset_quality_service
```

Explicit paths may be supplied with `--products`, `--images`, `--reviews`, `--market`, `--product-intelligence`, and `--master`.

