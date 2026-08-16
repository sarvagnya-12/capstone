# DryRunAI

A GAN-centric generative AI framework for pre-launch product simulation and product-market-fit optimization. Academic capstone project (BMS College of Engineering, Dept. of ISE, AY 2025-26).

## Documentation

- [`PRD.md`](PRD.md) — full product requirements, reconstructed from the certified capstone report and supporting documents.
- [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) — condensed technical context for fast session start.
- [`IMPLEMENTATION.md`](IMPLEMENTATION.md) — the final, step-by-step implementation plan. Single source of truth for build order and progress.

## Repository Layout

- `backend/` — FastAPI application (API, services, ML components, database models).
- `frontend/` — React application (dashboard, forms, simulation views).
- `scripts/` — standalone operational scripts (e.g. dataset-pipeline ingestion).
- `Capstone Docs/` — source PDFs the PRD was reconstructed from.
- `Capstone Dataset (Archived)/` — a separately maintained, out-of-scope dataset-extraction pipeline; consumed only as an external batch data source (see `IMPLEMENTATION.md` Phase 5).

See `IMPLEMENTATION.md` for current build status and the next step.
