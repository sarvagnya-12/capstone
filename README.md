# DryRunAI

A GAN-centric generative AI framework for pre-launch product simulation and product-market-fit optimization. Academic capstone project (BMS College of Engineering, Dept. of ISE, AY 2025-26).

A business uploads a product photo and a launch scenario; the system generates design variants, shows them to simulated customer personas, and reports which variant to take forward — in plain business terms — before anything is manufactured.

## Documentation

- [`REPORT.md`](REPORT.md) — **start here.** What was built, how it works, what changed from the plan and why, with measurements.
- [`IMPLEMENTATION.md`](IMPLEMENTATION.md) — the step-by-step plan, its resolved design decisions and per-step status. Single source of truth for build order and progress.
- [`PRD.md`](PRD.md) — the requirements, reconstructed from the certified capstone report (design-stage document; resolutions are in `IMPLEMENTATION.md`).
- [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) — condensed version of the PRD.
- [`GENERATOR_ALT.md`](GENERATOR_ALT.md) — the GAN vs diffusion analysis, and its measured outcome.
- [`TRAINING_TRANSFER.md`](TRAINING_TRANSFER.md) — running the large FastGAN training on another machine (optional).
- [`docs/deployment.md`](docs/deployment.md) — deployment runbook (Render).

## Repository Layout

- `backend/` — FastAPI application (API, services, ML components, database models), tests, and evaluation/training scripts in `backend/scripts/`.
- `frontend/` — React application (upload, scenario setup, progress, results dashboard, admin).
- `scripts/` — standalone operational scripts (dataset-pipeline ingestion).
- `Capstone Docs/` — source PDFs the PRD was reconstructed from.
- `Capstone Dataset (Archived)/` — a separately maintained dataset-extraction pipeline; consumed only as an external batch data source (see `IMPLEMENTATION.md` Phase 5).

## Local Development

Run each piece in its own terminal, from the repo root:

```
# 1. Database
docker compose up db

# 2. Backend (in backend/, after: python -m venv .venv; pip install -r requirements.txt; copy .env.example .env;
#    alembic upgrade head; python -m scripts.seed_personas)
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload

# 3. Frontend (in frontend/, after: npm install; copy .env.example .env)
cd frontend
npm run dev
```

Copy each `.env.example` (root, `backend/`, `frontend/`) to `.env` before first run — the defaults are consistent with each other. Replace `JWT_SECRET_KEY` before any non-local use.

With the defaults, the system runs the **GAN-only pipeline with a local Ollama model** (`ollama pull llama3.1:8b`). The full pipeline — diffusion rendering, the trained ESRGAN upscaler, personas that see the images, and review grounding — needs a Cloudflare API token, Ollama Cloud, the trained weights and the review index; `REPORT.md` §11 lists the exact settings, and `backend/.env.example` documents each one.

Run the tests from `backend/` with `python -m pytest -q`. They never call real APIs and ignore your `.env` pipeline settings.
