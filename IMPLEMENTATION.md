# IMPLEMENTATION.md — DryRunAI

**Status of this document:** Final, single-source-of-truth implementation plan. Supersedes any informal planning — if this document and a future ad-hoc suggestion disagree, this document wins unless explicitly revised.

**Built from:** `PRD.md` and `PROJECT_CONTEXT.md` (requirements authority), plus a direct inspection of the repository (confirmed: zero core-system code exists anywhere) and of the dataset-extraction pipeline's public interface at `Capstone Dataset (Archived)/Capstone Dataset/DryRunAI/schemas/*.json` (its internals remain out of scope, per standing project instruction).

## Decisions This Document Resolves

PRD.md §37 lists eleven open decisions and explicitly states none of them are resolved by that document. A step-by-step build plan cannot be non-vague while those remain open, so they are resolved **here**, with rationale. Nothing below contradicts a `[CONFIRMED]` fact in PRD.md — each resolves an `[OPEN DECISION]` or an either/or `[PROPOSED]` choice.

| # | Decision | Resolution | Rationale |
|---|---|---|---|
| 1 | Architecture scope (certified SRS vs. working Phase-3) | Build the certified 7-layer SRS architecture as the complete, working MVP (Phases 1–16 below). Phase-3 items (vector DB, multi-agent orchestration, Celery/Redis, MLOps) become Phase 17 — explicitly optional, built only after the MVP milestone. | Confirmed with project owner. Phase-3 was never certified; building it as core scope risks the academic timeline for value that isn't required by any functional requirement. |
| 2 | Tech stack (all either/or in SRS Table 5.5) | Backend: **FastAPI**. Frontend: **React** (Vite + TypeScript). Database: **PostgreSQL**. GAN framework: **PyTorch**. | Confirmed with project owner. FastAPI is the SRS's own "preferred for performance" option; the class diagram (Fig 6.3) is inherently relational, favoring Postgres over MongoDB; PyTorch has the stronger pretrained-GAN-checkpoint ecosystem (StyleGAN2/StyleGAN2-ADA). |
| 3 | Optimization-loop mechanism | **Heuristic/threshold weighting**: latent-space nudging + scenario-weighted scoring + threshold-based risk gating. No RL, no Bayesian/genetic search in the MVP. | Confirmed with project owner. Matches the Abstract/synopsis description exactly, and resolves the SRS's internal self-contradiction (FR table says RL; Scope section calls RL future work) in favor of the Scope section, which is more specific and appears in more sources. Feasible on the certified modest hardware (§28); RL/Bayesian/genetic all stay documented as Phase 17+/future. |
| 4 | Persona diversity mechanism | Curated library of **~20 predefined persona templates**, parameterized (age range, income segment, lifestyle, region, behavior traits) and grounded in `product_intelligence.csv` target-segment fields where available. Sampled per simulation, not hardcoded to 2–3 examples. Dynamic LLM-generated personas deferred to Phase 17. | Confirmed with project owner. Matches SRS §1.4's explicit current-scope statement ("predefined personas"), while still giving real variety — a meaningful improvement over the 2–3 examples that appear in every diagram. |
| 5 | GAN-centric framing vs. Stable Diffusion | Primary and only generative model in the MVP is a **GAN** (StyleGAN2, pretrained-checkpoint transfer learning). No diffusion model is built. | Preserves the certified "GAN-centric" title per the standing instruction not to silently pivot the core narrative. Stable Diffusion inclusion is not part of this plan at any phase; if desired later, it is a distinct decision requiring separate approval, not something this document schedules. |
| 6 | Training strategy vs. certified hardware (§21/§28) | **Transfer learning / fine-tuning from a pretrained StyleGAN2 checkpoint**, not training from scratch. Fine-tuning executed on a rented/free cloud GPU (e.g., Colab/Kaggle), not the certified local machine; the local machine handles inference, dev, and orchestration only. | Reconciles the literature survey's own repeated warnings that StyleGAN2-class models are computationally heavy with the modest certified hardware spec — the only way both statements can be true simultaneously. |
| 7 | Realism / diversity / consistency metrics (undocumented anywhere) | **FID score** (via `torchmetrics`) for generated-variant realism; a simple **persona-response consistency check** (re-run the same persona × variant pair, flag high output variance) for evaluator reliability. | Closes a real, flagged gap (PRD §16, §19, §31, Open Decision #5) with standard, low-effort tooling rather than leaving generation/evaluation quality entirely unmeasured. |
| 8 | Iteration-loop stopping criteria (undefined in Fig 6.4) | Configurable **max-iteration count (default 3)** OR **PMF-score-plateau** (recommendation score improves by less than a configurable threshold between iterations), whichever triggers first. | Closes Open Decision #6 with the simplest rule that prevents both premature stopping and unbounded looping. |
| 9 | Depth of "market simulation" | Product-market-fit score is explicitly an **aggregate of persona-level sentiment/engagement/purchase-intent** — not a separate economic/demand model. No competitor modeling, price elasticity, or demand forecasting is built. | Matches what is actually documented and buildable (PRD §17, Open Decision #7); stated explicitly so it reads as an intentional scope decision, not a missing feature. |
| 10 | "Microservices" (NFR, §10) vs. team size/timeline | Build a **modular monolith**: one FastAPI application with module boundaries that mirror the certified 7-layer architecture, not literal separate deployed services. | Deploying 5+ real microservices for a 4-person academic team is unnecessary complexity with no corresponding requirement forcing it; the module boundaries keep a future split possible without paying that cost now. |
| 11 | Admin (class diagram, Fig 6.3) | Modeled as a `role` column on the `User` table (`user` \| `admin`), not a separate table. | Reproduces the exact same relationships the class diagram specifies (Admin manages Users, monitors Simulations) without a redundant entity. |
| 12 | Dataset-pipeline integration mechanics (Open Decision #11) | A one-way, script-driven ingestion (`scripts/ingest_dataset_pipeline.py`) reads the pipeline's frozen CSV/Parquet outputs and schemas directly off disk into read-only `ref_*` tables in the core system's own Postgres database. No shared API, no shared DB, no live coupling. | The pipeline's own README states its outputs are frozen, versioned files (`datasets/versions/...`, `datasets/master/...|`) meant to be read, not a service to call. A file-based batch import is the natural, lowest-risk integration given that contract. |

Everything else in PRD.md §37 (pipeline-stage ordering, the literature review's unfilled per-member gaps table) is LOW priority and non-blocking for implementation; it is not re-litigated here.

**External prerequisite this document does not perform:** the dataset-extraction pipeline (`Capstone Dataset (Archived)/...`) currently has **zero real records** (`project_manifest.json`: every count is `0`; only 4-row test fixtures exist under `datasets/`). Running that pipeline end-to-end to produce real product/image/review/market/intelligence data is a prerequisite for Phase 6 Step 17 (GAN fine-tuning) and for Phase 5's ingestion having anything real to ingest. It is out of scope for this document (per standing instruction) — Phase 5 and Phase 6 note the fallback path (test fixtures / a small public image set) for development in the meantime.

---

# 1. Implementation Overview

DryRunAI is being built from zero code to a working system that satisfies all 10 certified functional requirements (PRD §9) and all 8 non-functional requirements (PRD §10), using the stack and decisions resolved above: **FastAPI + PostgreSQL backend, React frontend, PyTorch/StyleGAN2 for generation, an LLM-provider-agnostic persona engine, all wired together as a modular monolith.**

**Development sequence, at a glance:**

```
Foundation → Database → Auth → Product Upload → Dataset Ingestion
   → GAN Generation → Persona/LLM Simulation → Sentiment → Risk
   → Optimization Loop → Simulation Orchestration → Recommendation
   → Dashboard/Analytics API → Frontend → Testing → Deployment
   → (optional) Phase-3 Enhancements
```

The sequence follows the system's real data dependencies, not the order functional requirements are numbered in the SRS table: authentication must exist before anything it protects; a product must be uploaded before it can be varied; the dataset pipeline must be ingested before personas can be grounded in real target-segment data; GAN variants must exist before personas can react to them; persona feedback must exist before sentiment/risk/optimization/recommendation can run on it; and the API surface for each capability must exist before the frontend page that calls it.

Frontend work is **not** pushed entirely to the end — Phase 14 (frontend) begins as soon as Phase 3 (auth) and Phase 4 (product upload) expose working APIs, and grows alongside the backend so the system is demoable incrementally rather than only at the very end (see §6 Milestone Plan).

Every phase after Phase 4 that touches AI/ML (GAN, persona/LLM, sentiment, risk, optimization) is designed to be developed and unit-tested independently against fixtures, then wired together in Phase 11's orchestration step — this lets team members work on Phases 6–10 in parallel once Phase 5 exists (see §5 Dependency Order).

---

# 2. Current Project State

**What is already implemented:** Nothing. A direct filesystem check confirms there is no backend, frontend, database schema, API, or ML code anywhere in this repository for the core DryRunAI system.

**What is partially implemented:** Nothing. This is a from-zero build.

**What exists in the repository today:**
- `PRD.md`, `PROJECT_CONTEXT.md` — requirements sources (authoritative, unchanged by this document).
- `Capstone Docs/` — the five source PDFs the PRD was reconstructed from.
- `Capstone Dataset (Archived)/Capstone Dataset/DryRunAI/` — a separate, code-complete, **data-empty** ETL pipeline (7 services, all implemented, zero real records generated). Out of scope to modify or analyze beyond its public schema/taxonomy interface, per standing instruction. This plan treats its frozen output files as an external batch data source only (see Decision #12 above).
- `.claude/settings.local.json` — local tooling permission config, unrelated to application architecture.

**What is missing:** everything required to satisfy PRD §9 Functional Requirements #1–10 — authentication, product upload, scenario configuration, GAN generation, persona simulation, sentiment analysis, risk detection, feedback optimization, dashboard, and final recommendation. Also missing: any database, any API, any frontend, any deployment configuration, and version control itself (this directory is not a git repository yet).

**Existing technical decisions:** none pre-dated this document. The stack, architecture-scope, and mechanism decisions in "Decisions This Document Resolves" above are the first technical decisions made for the core system, and this plan is built directly on them.

**Existing problems / technical debt:**
1. **No version control.** Addressed as Step 1 — must happen before any other step.
2. **Dataset pipeline has zero real data.** Blocks real (non-fixture) GAN fine-tuning (Step 17) and limits Step 13/14 ingestion to test-fixture scale until the pipeline is separately run. Not a defect in this plan — an external dependency it correctly does not try to resolve.
3. **Certified hardware spec (i5/i7, 8GB RAM, "GPU recommended") is insufficient for local GAN fine-tuning.** Resolved by Decision #6 (cloud GPU for fine-tuning, local for inference) — flagged again at Step 17 where it matters concretely.

No completed work is re-described as future work anywhere below — every step in Section 4 is genuinely unbuilt.

---

# 3. Development Phases

| Phase | Name | Produces |
|---|---|---|
| 1 | Foundation & Environment Setup | Git repo, backend/frontend scaffolds, local dev environment |
| 2 | Database & Core Schema | All SQLAlchemy models, migrations, reference-data tables |
| 3 | Authentication & Authorization | Registration, JWT login, role-based access |
| 4 | Product Upload Module | Product CRUD, image storage, preprocessing |
| 5 | Dataset Pipeline Ingestion | `ref_*` tables populated, persona seed data extracted |
| 6 | GAN Product Generation Engine | Variant generation, fine-tuning pipeline, realism metric |
| 7 | Persona & LLM Simulation Engine | Persona library, LLM provider layer, reaction simulation |
| 8 | Sentiment Analysis | Sentiment classification service |
| 9 | Risk Detection | Rule-based risk-alert engine |
| 10 | Feedback-Driven Optimization Loop | Heuristic optimizer, iteration control |
| 11 | Scenario Configuration & Simulation Orchestration | End-to-end pipeline wiring behind one API |
| 12 | Final Recommendation Engine | Ranking/PMF scoring, recommendation API |
| 13 | Dashboard & Analytics API | Aggregation endpoints, report export |
| 14 | Frontend Application | Full React UI for every use case in Fig 6.5 |
| 15 | Testing & Hardening | Test suite, E2E pass, security review |
| 16 | Deployment | Containerized, deployed, verified system |
| 17 | Phase-3 Enhancements (optional) | Vector KB, async queue, dynamic personas, experiment tracking |

Phases 1–16 constitute the certified-scope MVP (Decision #1). Phase 17 is explicitly optional and only begins after the Phase 16 milestone (§6, M6) is reached.

---

# 4. Detailed Step-by-Step Implementation Plan

## Phase 1 — Foundation & Environment Setup

### Step 1 — Initialize Version Control & Repository Layout

**Status: ✅ Completed (2026-08-16).** Commit `3b79e25` — "Initial commit: project docs, archived dataset pipeline, and repo scaffold" (267 files).

**Implementation notes / deviations from the literal step text above:**
- **Initial commit scope was broadened.** The step text says to commit "the PRD/context docs and this file"; the actual initial commit also includes `Capstone Docs/*.pdf` (source requirement docs) and the archived dataset pipeline's source code (excluding its generated-data output). Rationale: nothing in the step said to exclude them, and the `.gitignore` carve-out for the pipeline's *data* only makes sense if its *code* stays tracked — excluding the whole archived folder would have made that distinction moot.
- **`.gitignore` dataset-pipeline pattern was refined**, not a blanket `**/datasets/`. The archived pipeline's `datasets/**/raw/` subfolders contain small (4-row) hand-authored fixture CSVs (`sample_zappos.csv`, `sample_amazon_reviews.csv`, `sample_market.csv`, `sample_product_intelligence.csv`) that Step 13 explicitly depends on being "already present in the repo." A blanket `**/datasets/` ignore would have excluded these. The final `.gitignore` instead targets only the known *output* directories (`merged/`, `normalized/`, `versions/`, `assets/`, `quarantine/`, `master/`, and each service's `processed/`, `quarantine/`, `versions/`, `reports/`, `metadata/` subfolders, plus every `logs/`/`output/` directory) — all currently empty (`dataset_health_score: 0`), so nothing was lost by ignoring them, and the raw fixtures remain tracked.
- **Added `.claude/settings.local.json` to `.gitignore`** (not specified in the step text) — machine-local tooling config, not called out explicitly, but consistent with a per-user config file, verified before excluding.

#### When
First step, before anything else. No code can be safely written without version control.

#### Objective
Turn this directory into a git repository with the top-level layout every later step assumes.

#### What to Develop
- Git repository initialization.
- Top-level directory skeleton: `backend/`, `frontend/`, `scripts/`, plus root config files.
- `.gitignore` covering Python, Node, environment files, and local storage.

#### Files to Create
- `.gitignore`
- `backend/` (empty directory placeholders: `app/`, `tests/`)
- `frontend/` (empty directory placeholder)
- `scripts/` (empty directory placeholder)
- `README.md` (short: project name, pointer to `PRD.md`, `PROJECT_CONTEXT.md`, this file)

#### Files to Modify
None — nothing exists yet.

#### Implementation Details
Run `git init` in `g:/Capstone`. Do **not** add `Capstone Dataset (Archived)/` datasets or any future `backend/storage/` contents to version control — `.gitignore` must exclude `**/datasets/`, `backend/storage/`, `.env`, `__pycache__/`, `node_modules/`, `*.pt`/`*.pth` (model checkpoints), and `.venv/`. Commit the PRD/context docs and this file as the initial commit so history starts from a known-good state.

#### Dependencies
None.

#### Expected Result
A git repository with an initial commit containing the existing docs, `.gitignore`, and empty scaffold directories.

#### Verification
`git status` shows a clean working tree after the initial commit; `git log` shows one commit.

#### Completion Criteria
Repository is git-initialized, `.gitignore` is in place and correct, initial commit exists.

---

### Step 2 — Backend Project Scaffold (FastAPI)

**Status: ✅ Completed (2026-08-17).**

**Implementation notes / deviations from the literal step text above:**
- **`LLM_PROVIDER` was deliberately left out** of `Settings` in this step, despite being named in the Implementation Details paragraph above — Step 20's own text lists `core/config.py` under its "Files to Modify" with the explicit action "add `LLM_PROVIDER`...", confirming that field belongs to Step 20, not here. Settings implemented now: `DATABASE_URL`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES`, `STORAGE_ROOT`, `ENVIRONMENT`.
- **Added `CORS_ORIGINS`** (comma-separated, default `http://localhost:5173`) — not named as a field in the plan text, but required to fulfil the same paragraph's "mounts a CORS middleware (configurable allowed origins...)" sentence. Verified via a real CORS preflight request.
- **Structured JSON logging** implemented with a small inline formatter class in `main.py` (standard library `logging` only, no new dependency) rather than a separate file, since no logging-specific file was listed in "Files to Create." Note: this configures the *root* logger — Uvicorn's own `uvicorn`/`uvicorn.error` loggers install their own handlers/formatting on top (standard Uvicorn behavior) and stay in Uvicorn's default text format; application code's own loggers (added from Step 11 onward) will flow through the JSON root handler as intended.
- **`requirements.txt` locked to exact versions**, not the minimum-version floors originally drafted — installed the plan's 12 named packages fresh, confirmed a clean install (`pip check`: no broken requirements) and a working server, then pinned to the exact resolved versions (`fastapi==0.141.1`, `uvicorn[standard]==0.52.3`, `pydantic-settings==2.15.0`, `sqlalchemy==2.0.52`, `alembic==1.19.1`, `psycopg[binary]==3.3.4`, `passlib[bcrypt]==1.7.4`, `python-jose[cryptography]==3.5.0`, `python-multipart==0.0.32`, `pillow==12.3.0`, `pytest==9.1.1`, `httpx==0.28.1`) for reproducibility.
- **Deleted `backend/app/.gitkeep`** — redundant now that `app/` contains real files (mirrors the same convention used for the dataset pipeline's placeholders, noted in Step 1).
- Confirmed this machine's Python must be invoked as `python`, not `python3` (the latter hits the Windows Store alias stub) — relevant for every future step's commands.

#### When
Immediately after Step 1. Every backend step depends on this scaffold existing.

#### Objective
Stand up a minimal, runnable FastAPI application with configuration loading, before any real endpoints exist.

#### What to Develop
- Python package structure for the backend.
- Environment-variable-based configuration (`Settings` object).
- A minimal FastAPI app that starts and exposes a health-check endpoint.

#### Files to Create
- `backend/requirements.txt`
- `backend/app/__init__.py`
- `backend/app/main.py`
- `backend/app/core/__init__.py`
- `backend/app/core/config.py`
- `backend/.env.example`

#### Files to Modify
None.

#### Implementation Details
`requirements.txt` pins: `fastapi`, `uvicorn[standard]`, `pydantic-settings`, `sqlalchemy`, `alembic`, `psycopg[binary]`, `passlib[bcrypt]`, `python-jose[cryptography]`, `python-multipart`, `pillow`, `pytest`, `httpx` (for tests). ML/LLM-specific packages are added in their own phases (Steps 15, 20, 23) rather than all at once, so each phase's dependency footprint is traceable to the step that needed it.

`core/config.py` defines a `pydantic-settings` `Settings` class reading: `DATABASE_URL`, `JWT_SECRET_KEY`, `JWT_ALGORITHM` (default `HS256`), `JWT_EXPIRE_MINUTES`, `STORAGE_ROOT` (local file storage path), `LLM_PROVIDER` and its API key variable(s) (added fully in Step 20), `ENVIRONMENT` (`dev`/`prod`). `.env.example` documents every variable with a placeholder value and a one-line comment — never a real secret.

`main.py` creates the FastAPI app, mounts a CORS middleware (configurable allowed origins for local frontend dev), configures structured logging (Python's standard `logging` module, JSON-formatted, level from `Settings.ENVIRONMENT`) so every later service's error/failure paths (Steps 11, 21, 28, etc.) have a consistent place to log to from day one, and exposes `GET /health` returning `{"status": "ok"}`. No business routers are mounted yet — they're added incrementally in later phases.

#### Dependencies
Step 1 (repo layout).

#### Expected Result
Running `uvicorn app.main:app --reload` from `backend/` starts a server; `GET /health` returns 200.

#### Verification
```
cd backend
python -m venv .venv
.venv\Scripts\activate  (or source .venv/bin/activate on non-Windows)
pip install -r requirements.txt
copy .env.example .env   (edit values)
uvicorn app.main:app --reload
```
Then `curl http://localhost:8000/health` returns `{"status":"ok"}`.

#### Completion Criteria
Backend starts without error; health check responds; `.env.example` documents all variables in use so far.

---

### Step 3 — Frontend Project Scaffold (React + Vite)

**Status: ✅ Completed (2026-08-17).**

**Implementation notes / deviations from the literal step text above:**
- **Route list corrected against what Phase 14 actually expects later.** The original text above listed `/reports` as a stub route, but no later step (Steps 33–37) ever creates or references a `ReportsPage` — report download ends up as a button on `DashboardPage` (Step 37). Meanwhile Step 35 explicitly expects to "replace a placeholder" for `SimulationRunPage.tsx` at `/simulations/:id`, which the original route list never included. Implemented routes/pages: `/login` (LoginPage), `/register` (RegisterPage), `/products/new` (ProductUploadPage), `/simulations/new` (ScenarioConfigPage), `/simulations/:id` (SimulationRunPage — added), `/dashboard` (DashboardPage), `/admin` (AdminPage) — `/reports` dropped. Root `/` redirects to `/login`. Discussed with and approved by the user before implementing.
- **`fetch` chosen over `axios`** for `api/client.ts` (the plan left this as "axios (or native fetch wrapper)") — a thin `apiFetch<T>()` wrapper handles JSON headers and error unwrapping in one place, avoiding an extra dependency the stack doesn't need.
- **Tooling reflects the current Vite scaffold** (`create-vite@9.1.2`): React 19, Vite 8, TypeScript 6.0, and `oxlint` in place of ESLint (the template's own current default linter) — not a deviation from intent, just what "the standard template" now produces. `tsconfig.json` split into `tsconfig.json`/`tsconfig.app.json`/`tsconfig.node.json` per current Vite convention.
- Removed the template's demo content (hero/counter/doc-links in `App.tsx`, its demo assets and CSS) and its own nested `.gitignore`/`README.md` (redundant with the root `.gitignore` from Step 1) as part of scaffolding — `App.tsx` is now a minimal layout shell rendering an `<Outlet />`.

#### When
Can be done in parallel with Step 2 (independent toolchains) once Step 1 is complete.

#### Objective
Stand up a minimal, runnable React application shell with routing and an API client stub, before any real pages exist.

#### What to Develop
- Vite + React + TypeScript project.
- Client-side router with placeholder routes.
- A typed API client stub pointing at the backend's base URL.

#### Files to Create
- `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/index.html`
- `frontend/src/main.tsx`, `frontend/src/App.tsx`
- `frontend/src/router.tsx`
- `frontend/src/api/client.ts`
- `frontend/.env.example`

#### Files to Modify
None.

#### Implementation Details
Scaffold via `npm create vite@latest frontend -- --template react-ts`. Add `react-router-dom` for routing and `axios` (or native `fetch` wrapper) for the API client. `api/client.ts` reads `VITE_API_BASE_URL` from `.env` (default `http://localhost:8000`) and exports a configured client with a placeholder for attaching the JWT auth header (implemented fully in Step 32). `router.tsx` declares routes for every page named in PRD §25/Fig 6.5 as placeholder stub components for now: `/login`, `/register`, `/products/new`, `/simulations/new`, `/dashboard`, `/reports`, `/admin` — actual page implementations land in Phase 14.

#### Dependencies
Step 1 (repo layout). Independent of Step 2.

#### Expected Result
`npm run dev` starts the Vite dev server and renders a placeholder app shell with working client-side routing between stub pages.

#### Verification
```
cd frontend
npm install
copy .env.example .env
npm run dev
```
Visiting each stub route in a browser renders its placeholder without a console error.

#### Completion Criteria
Frontend dev server starts cleanly; all placeholder routes render; API client is configured but not yet exercised against real endpoints.

---

### Step 4 — Local Development Environment

**Status: ✅ Completed (2026-08-17).**

**Implementation notes / deviations from the literal step text above:**
- **`backend/app/core/config.py` needed no actual change** — `DATABASE_URL` was already set correctly in `backend/.env.example` back in Step 2 (with a comment already anticipating this step). The "Files to Modify" line was satisfied by confirmation, not an edit.
- **`README.md` documentation added** despite not being explicitly listed under Step 4's "Files to Modify" — the Implementation Details paragraph above explicitly calls for it ("Document in `README.md` the three-terminal local workflow"), so it was treated as required.
- **Blocking discovery, resolved with the user before implementing:** Docker was not installed on this machine at all when this step was first attempted (no `docker` command, no WSL2, no admin rights available in-session to install either). The user installed Docker Desktop themselves (with WSL2) between sessions. Verification then required working around a stale `PATH` in the assistant's own shell session (Docker's install location was correctly in the machine-level `PATH`, just not yet in already-open shell processes) — resolved by prefixing the full path in verification commands; does not affect the user's own terminal sessions.
- Verification went beyond `pg_isready` — also confirmed a real SQLAlchemy connection using the backend's actual `Settings`/`.env` (`SELECT 1`, `SHOW server_version` → Postgres 16.15), which is the strongest available proof of this step's actual Expected Result.

#### When
After Steps 2 and 3 exist (it wires both together with a database).

#### Objective
Give every later step a single, reproducible way to run Postgres + backend + frontend locally.

#### What to Develop
- Docker Compose definition for local Postgres (backend/frontend run natively during development for fast reload; containerized fully in Phase 16).
- Root-level environment variable documentation.

#### Files to Create
- `docker-compose.yml` (root) — Postgres service only, for local dev.
- `.env.example` (root, documents `POSTGRES_*` vars consumed by `docker-compose.yml`)

#### Files to Modify
- `backend/app/core/config.py` — confirm `DATABASE_URL` format matches the compose Postgres service (`postgresql+psycopg://dryrunai:dryrunai@localhost:5432/dryrunai`).

#### Implementation Details
`docker-compose.yml` defines a single `db` service (`postgres:16`), with a named volume for persistence and health check. Document in `README.md` the three-terminal local workflow: `docker compose up db`, backend `uvicorn` reload server, frontend `npm run dev`. Full multi-service containerization (backend + frontend images) is deliberately deferred to Phase 16 — building it now would be premature before there's an application to containerize.

#### Dependencies
Steps 2, 3.

#### Expected Result
A developer can bring up Postgres with one command and point the backend at it via `DATABASE_URL`.

#### Verification
`docker compose up db` starts Postgres; `psql` or any Postgres client can connect using the documented credentials; backend `.env`'s `DATABASE_URL` matches.

#### Completion Criteria
Postgres reachable locally via Docker Compose; `README.md` documents the full local dev startup sequence.

---

## Phase 2 — Database & Core Schema

### Step 5 — Core Domain Models (SQLAlchemy)

**Status: ✅ Completed (2026-08-17).**

**Implementation notes / decisions made (implemented directly, >95% confidence, per user's fast-track instruction):**
- SQLAlchemy 2.0 typed-declarative style (`Mapped`/`mapped_column`) throughout; `Uuid` PKs with `uuid.uuid4` defaults; `JSONB` (not generic `JSON`) for all JSON columns, since the stack is Postgres-committed and JSONB is strictly better there.
- `models/__init__.py` proactively imports and re-exports every model (beyond Step 5's own verification command) so `import app.models` alone registers the full schema on `Base.metadata` — this directly sets up what Step 6's Alembic `env.py` needs.
- `ondelete` FK behavior set now, on the models, rather than deferred to hand-editing the Step 6 migration (Alembic reads `ondelete` from the model's `ForeignKey`, so this is the natural place for it): `CASCADE` for Product→{Simulation,ProductVariant}, Simulation→{ProductVariant,Feedback,Recommendation}; `RESTRICT` for User→{Product,Simulation} and Feedback/SimulationPersona→Persona (personas are shared reference data, not simulation-owned) and Recommendation→ProductVariant. Step 6's plan text explicitly named a subset of these (Product→ProductVariant CASCADE, Simulation→Feedback/Recommendation CASCADE, User→Product RESTRICT); the rest follow the same stated logic applied consistently to structurally identical relationships.
- `feedback.sentiment_label/sentiment_score/engagement_score/risk_flags` are nullable — populated in stages by later steps (21 → 23 → 24), not all at once.
- Verification went beyond the step's own import check: forced `configure_mappers()` (catches relationship/FK errors the plain import wouldn't), and ran a real `create_all()`/`drop_all()` against actual Postgres to confirm DDL (enums, JSONB, FK `ondelete`) is valid before Step 6 builds the migration on top of it.

#### When
Immediately after Phase 1. Every feature from here on persists data, so the schema must exist first.

#### Objective
Define every persistent entity required by the certified class diagram (PRD §12, Fig 6.3), plus the one necessary elaboration (`ProductVariant`) needed to make Feedback's relationships work.

#### What to Develop
SQLAlchemy ORM models for: `User`, `Product`, `ProductVariant`, `Simulation`, `Persona`, `SimulationPersona` (association), `Feedback`, `Recommendation`.

#### Files to Create
- `backend/app/db/__init__.py`
- `backend/app/db/base.py` (declarative base, shared mixins for `id`/timestamps)
- `backend/app/models/__init__.py`
- `backend/app/models/user.py`
- `backend/app/models/product.py`
- `backend/app/models/product_variant.py`
- `backend/app/models/simulation.py`
- `backend/app/models/persona.py`
- `backend/app/models/feedback.py`
- `backend/app/models/recommendation.py`

#### Files to Modify
None.

#### Implementation Details
Schema (columns abbreviated to name:type; all tables get `id: UUID PK`, `created_at: timestamptz`):

- **users**: `org_name:str`, `email:str unique`, `hashed_password:str`, `role:enum[user,admin] default user` (resolves Decision #11).
- **products**: `user_id:FK users`, `name:str`, `description:text`, `brand:str null`, `category:str`, `branding_details:text null`, `original_image_path:str`, `preprocessed_image_path:str null`.
- **product_variants**: `product_id:FK products`, `simulation_id:FK simulations`, `image_path:str`, `attributes:JSON` (`{color, texture, layout, branding_style}`), `generation_method:str`, `fid_score:float null`.
- **simulations**: `product_id:FK products`, `user_id:FK users`, `pricing_strategy:JSON`, `target_demographic:JSON`, `promotional_messaging:text null`, `status:enum[pending,generating,simulating,evaluating,optimizing,completed,failed]`, `iteration_count:int default 0`, `max_iterations:int default 3`, `completed_at:timestamptz null`.
- **personas**: `template_key:str unique`, `name:str`, `age_min:int`, `age_max:int`, `income_segment:str`, `lifestyle:str`, `region:str`, `gender:str null`, `behavior_traits:JSON`, `prompt_template:text`, `source:enum[seeded,dynamic] default seeded`.
- **simulation_personas**: composite PK (`simulation_id`, `persona_id`) — many-to-many, matches "Simulation uses one-or-more Personas" (PRD §12).
- **feedback**: `simulation_id:FK simulations`, `variant_id:FK product_variants`, `persona_id:FK personas`, `qualitative_text:text`, `purchase_likelihood:float`, `sentiment_label:enum[positive,negative,neutral]`, `sentiment_score:float`, `engagement_score:float`, `risk_flags:JSON`, `consistency_variance:float null`, `iteration_number:int`.
- **recommendations**: `simulation_id:FK simulations`, `recommended_variant_id:FK product_variants`, `pmf_score:float`, `ranking:JSON`, `summary_text:text`.

`ProductVariant` is not a named class in Fig 6.3 — document this in a code comment on the model: "necessary elaboration: Feedback must reference a specific generated variant, not just the parent Product; the certified class diagram implies this via 'GAN generates synthetic variations' (FR#4) without naming the entity."

#### Dependencies
Step 4 (Postgres reachable), Step 2 (backend scaffold).

#### Expected Result
All ORM models importable, relationships correctly declared (`relationship()` both directions where used), no circular import errors.

#### Verification
`python -c "from app.models import user, product, product_variant, simulation, persona, feedback, recommendation"` from `backend/` exits without error.

#### Completion Criteria
Every entity in the class diagram is represented (directly or, for Admin, via `role`); `ProductVariant`'s deviation is documented inline; models import cleanly.

---

### Step 6 — Alembic Migration Setup & Initial Migration

**Status: ✅ Completed (2026-08-17).**

**Implementation notes / decisions made (implemented directly, per user's fast-track instruction):**
- Migration file named `0001_initial_schema.py` (matching the plan's naming convention) by generating with `alembic revision --rev-id 0001`, rather than accepting Alembic's default opaque-hash revision ID.
- **Real bug caught by the round-trip verification this step requires**: Alembic's autogenerate does not emit `DROP TYPE` for Postgres native enums in `downgrade()` — it only manages tables/columns, treating named enum types as out of scope. The first `alembic downgrade base` → `alembic upgrade head` cycle failed with `DuplicateObject: type "persona_source" already exists`, because the 4 enum types (`user_role`, `simulation_status`, `persona_source`, `sentiment_label`) survived the downgrade. Fixed by adding explicit `sa.Enum(name=...).drop(op.get_bind(), checkfirst=False)` calls at the end of `downgrade()` for all four types, after their dependent tables are dropped. Re-ran the full upgrade → downgrade → upgrade cycle clean afterward. This is exactly the kind of issue the plan's own verification step (a real round-trip, not just applying once) is designed to catch.
- `alembic/env.py` reads `DATABASE_URL` from `app.core.config.settings` (not `alembic.ini`'s static value) — `alembic.ini`'s `sqlalchemy.url` left blank with a comment pointing to this.

#### When
Immediately after Step 5.

#### Objective
Get the schema from Step 5 into an actual Postgres database, via a repeatable, versioned migration — not ad-hoc `create_all()` calls.

#### What to Develop
- Alembic configuration wired to the models from Step 5.
- Initial migration creating every table, FK, and index.

#### Files to Create
- `backend/alembic.ini`
- `backend/alembic/env.py`
- `backend/alembic/versions/0001_initial_schema.py`
- `backend/app/db/session.py` (engine + `SessionLocal` + FastAPI `get_db` dependency)

#### Files to Modify
- `backend/app/main.py` — no direct change required, but confirm no leftover `Base.metadata.create_all()` calls exist anywhere (migrations are the only schema-creation path from this step forward).

#### Implementation Details
`alembic/env.py` imports `Base` from `app.db.base` and all model modules (so `Base.metadata` is fully populated) and reads `DATABASE_URL` from `app.core.config.Settings`. Generate the initial revision with `alembic revision --autogenerate -m "initial schema"`, then hand-review the generated migration for correct FK ON DELETE behavior (`CASCADE` from `Product`→`ProductVariant`, `Simulation`→`Feedback`/`Recommendation`; `RESTRICT` from `User`→`Product` to avoid orphaning by accident) before applying it.

#### Dependencies
Step 5.

#### Expected Result
`alembic upgrade head` creates every table from Step 5 in the local Postgres instance, with correct constraints.

#### Verification
```
cd backend
alembic upgrade head
```
Then inspect via `psql -c "\dt"` — all 7 core tables (plus `simulation_personas`) exist. `alembic downgrade base` followed by `alembic upgrade head` round-trips cleanly.

#### Completion Criteria
Migration applies cleanly from empty DB to full schema and back; `get_db` dependency is importable and yields a working session.

---

### Step 7 — Reference-Data Tables for Dataset-Pipeline Ingestion

#### When
Immediately after Step 6 — same migration cycle, kept as a distinct step because these tables serve a different purpose (external reference data, not application state) and resolve a distinct open decision (#12).

**Status: ✅ Completed (2026-08-17).**

**Implementation notes / decisions made (implemented directly, per user's fast-track instruction):**
- No `IDMixin`/`TimestampMixin` reuse from Step 5 — each `ref_*` table uses the pipeline's own natural string key as its primary key (`product_id`, `image_id`, `review_id`, `market_record_id`, `intelligence_record_id`) rather than a synthetic UUID, since these mirror an external system's identifiers rather than being application-owned entities.
- `market_type`/`price_type`/`availability` (enumerated in the pipeline's own `market_schema.json`) stored as plain `String`, not Postgres native enums — their vocabulary is owned/validated by the external pipeline, not this application, and avoids the enum-type migration friction just hit in Step 6.
- Full round-trip (upgrade → downgrade → upgrade, both partial to `0001` and full to base) verified clean with no manual fixes needed this time.

#### Objective
Create the read-only tables that will hold the dataset-extraction pipeline's output once ingested (Phase 5), namespaced separately from application data so there's no ambiguity between "a product a user uploaded" and "a reference product from the pipeline's catalog."

#### What to Develop
SQLAlchemy models + migration for `ref_products`, `ref_images`, `ref_reviews`, `ref_market`, `ref_product_intelligence`, mirroring the pipeline's own frozen schemas column-for-column.

#### Files to Create
- `backend/app/models/reference_data.py`
- `backend/alembic/versions/0002_reference_tables.py`

#### Files to Modify
- `backend/app/db/base.py` — none needed if `Base` is already shared; ensure `reference_data.py` models are imported in `alembic/env.py`.

#### Implementation Details
Column sets copied exactly from the pipeline's schema files (verified during planning):
- `ref_products` ← `schemas/master_products_schema.json`: `product_id, brand, model, category, subcategory, gender, retail_price, release_year, primary_color, secondary_color, material, source, source_url, image_refs:JSON, review_refs:JSON, market_record_refs:JSON, product_intelligence_refs:JSON, provenance:JSON, relationship_counts:JSON, status`.
- `ref_images` ← `schemas/images_schema.json`: `image_id, product_id, source, source_url, original_image_url, image_type, width, height, aspect_ratio, file_size, sha256, image_format, download_timestamp, status, original_filename`.
- `ref_reviews` ← `schemas/reviews_schema.json`: `review_id, product_id, source, source_url, source_review_id, review_title, review_text, rating, review_date, reviewer_name, verified_purchase, helpful_votes, language, collected_at, status`.
- `ref_market` ← `schemas/market_schema.json`: `market_record_id, product_id, source, source_url, market_type, price_type, currency, price, availability, stock_status, release_date, region, last_updated, status`.
- `ref_product_intelligence` ← `schemas/product_intelligence_schema.json`: `intelligence_record_id, product_id, brand, source, source_url, brand_description, brand_mission, brand_values, campaign_name, campaign_description, campaign_theme, marketing_strategy, target_age_min, target_age_max, target_gender, target_income_segment, target_region, target_lifestyle, brand_positioning, brand_ambassador, tagline, product_family, parent_company, country_of_origin, launch_region, distribution_channels, sustainability_notes, competitor_products, competitor_brands, collected_at, status`.

Every `ref_*` table additionally gets `ingested_at:timestamptz` and `source_dataset_version:str` (not present in the pipeline's schema — added here to track which ingestion run populated the row). These tables have no FK relationships into the application's own tables (`products`, etc.) — they are a read-only reference corpus queried by `product_id`/joins at the application layer, not foreign-keyed into it, since the pipeline's `product_id`s are a separate namespace from application `products.id`.

#### Dependencies
Step 6. Requires the schema field names verified against the pipeline's `schemas/*.json` during planning (see "Decisions This Document Resolves" table).

#### Expected Result
Five new empty reference tables exist in the database, ready to receive data from the Phase 5 ingestion script.

#### Verification
`alembic upgrade head` creates the five `ref_*` tables; `psql -c "\d ref_products"` shows columns matching the pipeline schema exactly.

#### Completion Criteria
All five reference tables exist with correct column sets; no FK coupling to application tables; migration is reversible.

---

## Phase 3 — Authentication & Authorization

### Step 8 — User Registration & Password Handling

#### When
Immediately after Phase 2. Nothing else can be meaningfully built or tested behind auth until this exists.

**Status: ✅ Completed (2026-08-17).**

**Implementation notes / decisions made (implemented directly, per user's fast-track instruction):**
- Added `email-validator` to `requirements.txt` (not named in the plan text) — required at runtime by Pydantic's `EmailStr`, which the plan does specify using.
- **Real bug caught by testing, not just writing the code**: `passlib==1.7.4` (unmaintained since 2020) crashes with a `ValueError: password cannot be longer than 72 bytes` during its own internal backend self-test when paired with modern `bcrypt` (resolved to `5.0.0` back in Step 2) — a known passlib/bcrypt incompatibility, not anything wrong with the request. Fixed by explicitly pinning `bcrypt==4.0.1` (the standard, documented workaround) in `requirements.txt`. Confirmed working directly (`hash_password`/`verify_password`) before re-testing the full API.
- Verified beyond the plan's own curl example: also tested weak-password (422) and invalid-email (422) rejection, and queried the `users` table directly to confirm the stored value is a real bcrypt hash (`$2b$...`, 60 chars), never the plaintext password.

#### Objective
Let an organization register an account, satisfying FR#1's "Credentials, org details → Authentication, validation → Secure session" (PRD §9).

#### What to Develop
- Pydantic request/response schemas for registration.
- Password hashing.
- `POST /api/v1/auth/register` endpoint.

#### Files to Create
- `backend/app/schemas/__init__.py`
- `backend/app/schemas/auth.py`
- `backend/app/core/security.py` (password hashing helpers)
- `backend/app/services/__init__.py`
- `backend/app/services/auth_service.py`
- `backend/app/api/__init__.py`
- `backend/app/api/v1/__init__.py`
- `backend/app/api/v1/router.py`
- `backend/app/api/v1/auth.py`

#### Files to Modify
- `backend/app/main.py` — mount `api/v1/router.py` under `/api/v1`.

#### Implementation Details
`core/security.py` uses `passlib.context.CryptContext` with `bcrypt`. `schemas/auth.py` defines `RegisterRequest` (`org_name`, `email`, `password`, confirm via Pydantic `EmailStr` validation) and `UserResponse` (never includes the hash). `auth_service.register_user()` checks email uniqueness, hashes the password, inserts a `User` row with `role="user"`. Reject weak/empty passwords with a minimum-length validator (input validation at the system boundary, per project-wide security guidance).

#### Dependencies
Step 7 (schema/DB ready), Step 6 (`get_db` dependency).

#### Expected Result
`POST /api/v1/auth/register` with valid JSON creates a user and returns their public profile (no password/hash); duplicate email returns 409.

#### Verification
```
curl -X POST http://localhost:8000/api/v1/auth/register -H "Content-Type: application/json" -d "{\"org_name\":\"Acme\",\"email\":\"a@acme.com\",\"password\":\"correcthorse123\"}"
```
Returns 201 with user profile; a second identical call returns 409; row appears in `users` table with a bcrypt hash, not plaintext.

#### Completion Criteria
Registration works, rejects duplicates and weak passwords, never returns or logs the raw password.

---

### Step 9 — JWT Login & Auth Dependency

#### When
Immediately after Step 8.

**Status: ✅ Completed (2026-08-17).**

**Implementation notes / decisions made (implemented directly, per user's fast-track instruction):**
- **`get_current_admin_user` deliberately left out of this step**, despite being named in Step 9's own summary line ("Files to Modify: `core/deps.py` (new) — `get_current_user`, `get_current_admin_user` dependencies") — Step 10 is the dedicated step for it with its own full Implementation Details/Verification, and Step 9's own Implementation Details paragraph only ever describes `get_current_user`'s behavior. Same kind of plan-internal overlap as Step 3's route list; resolved the same way (defer to the step that actually owns it).
- `POST /login` uses FastAPI's standard `OAuth2PasswordRequestForm` (form-encoded `username`/`password`) rather than a JSON body — this is what makes `OAuth2PasswordBearer(tokenUrl=...)` and the auto-generated docs' "Authorize" button work correctly, and needed no new request schema, consistent with the step's own "no new files" note.
- Added `GET /auth/me` (not explicitly listed in the plan) — rather than a throwaway test route to verify `get_current_user`, this is a genuinely useful, permanent endpoint the frontend will need in Step 32 anyway, and doubled as the verification target.
- Verified beyond the plan's own suggestion: also explicitly tested wrong-password login (401), a corrupted token (401), and a token with a deliberately-past `exp` claim (401) — the completion criteria specifically calls out rejecting expired tokens, so this was tested directly rather than assumed from `python-jose`'s behavior.

#### Objective
Let a registered user obtain a session token, and give every future protected endpoint a reusable "current user" dependency — satisfying the NFR requirement for JWT-based secure login (PRD §10).

#### What to Develop
- `POST /api/v1/auth/login` issuing a JWT.
- A FastAPI dependency (`get_current_user`) that validates the JWT and loads the user.

#### Files to Create
None beyond additions to existing files.

#### Files to Modify
- `backend/app/core/security.py` — add JWT encode/decode helpers (`python-jose`).
- `backend/app/services/auth_service.py` — add `authenticate_user()`.
- `backend/app/api/v1/auth.py` — add `POST /login`.
- `backend/app/core/deps.py` (new) — `get_current_user`, `get_current_admin_user` dependencies.

#### Implementation Details
`login` verifies email + password via `passlib.verify`, then issues a JWT (`sub`=user id, `role`, `exp` from `JWT_EXPIRE_MINUTES`) signed with `JWT_SECRET_KEY`/`JWT_ALGORITHM` from settings. `core/deps.py`'s `get_current_user` uses `OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")`, decodes the token, 401s on invalid/expired tokens, and loads the `User` row. No refresh-token flow is built — a single short-lived access token is sufficient for the SRS's stated requirement ("JWT/OAuth-based secure login") and avoids unneeded complexity.

#### Dependencies
Step 8.

#### Expected Result
A registered user can log in and receive a JWT; that JWT, sent as a `Bearer` header, resolves to the correct user on any endpoint using `get_current_user`.

#### Verification
Log in via curl, capture the token, call a temporary protected test route (or reuse Step 11's product-create endpoint once it exists) with `Authorization: Bearer <token>` — succeeds; omitting/corrupting the header returns 401.

#### Completion Criteria
Login issues a valid JWT; `get_current_user` correctly accepts valid tokens and rejects missing/invalid/expired ones.

---

### Step 10 — Role-Based Access Control (User/Admin)

#### When
Immediately after Step 9.

**Status: ✅ Completed (2026-08-17).**

**Implementation notes / decisions made (implemented directly, per user's fast-track instruction):**
- `get_current_admin_user` implemented here (deferred from Step 9, see that step's notes).
- **Verification used an ad-hoc, in-process-only test route** (registered on the app only inside a throwaway verification script via `TestClient`, never written to any file) rather than inventing a real admin API endpoint prematurely — a real admin-only endpoint is Phase 13's job, once there's actual admin data to protect. This exercises the real FastAPI dependency-injection chain (`get_current_admin_user` → `get_current_user` → JWT decode → DB lookup) without adding fake permanent surface area to the API.

#### Objective

#### Objective
Give admin-only endpoints (Phase 13's admin views) a reusable guard, satisfying the Admin actor's responsibilities in Fig 6.3 ("manages users, monitors simulations").

#### What to Develop
`get_current_admin_user` dependency (builds on `get_current_user`, additionally requires `role == "admin"`).

#### Files to Create
None.

#### Files to Modify
- `backend/app/core/deps.py` — add `get_current_admin_user`.
- `backend/app/services/auth_service.py` — add an internal-only helper to promote a user to admin (no public endpoint for this in the MVP — done via direct DB update or a seed script, since self-service admin promotion is a security risk not required by any FR).

#### Implementation Details
`get_current_admin_user` depends on `get_current_user`, then raises 403 if `role != "admin"`. Document in code that admin promotion is intentionally not exposed via API — it's an operational action (DB update or a one-off seed script), consistent with least-privilege and with the SRS not specifying an admin-signup flow.

#### Dependencies
Step 9.

#### Expected Result
A dependency exists that Phase 13's admin endpoints can require, correctly separating normal users from admins.

#### Verification
Manually flip a test user's `role` to `admin` in the DB; confirm a route guarded by `get_current_admin_user` accepts that user and rejects a `role="user"` account with 403.

#### Completion Criteria
Role check works correctly in both directions; no public API path exists to self-promote to admin.

---

## Phase 4 — Product Upload Module

### Step 11 — Product CRUD API & Image Upload/Storage

#### When
Immediately after Phase 3. This is FR#2 (PRD §9) and the first endpoint real frontend work (Phase 14) will call.

**Status: ✅ Completed (2026-08-17).**

**Implementation notes / decisions made (implemented directly, per user's fast-track instruction):**
- No separate "create" Pydantic schema for the request — `POST /products` is `multipart/form-data` (file + fields), which FastAPI handles via individual `Form(...)`/`File(...)` parameters directly on the route, not a bound Pydantic model. Only `ProductResponse` was added to `schemas/product.py`.
- Product UUID generated up front (`uuid.uuid4()` in `product_service.create_product`) so the storage path `STORAGE_ROOT/products/{product_id}/` is known before the DB insert, matching the path convention the plan specifies.
- Non-owner requests to `GET /products/{id}` return 404 ("Product not found"), not 403 — deliberately avoids leaking existence of another user's resources; same pattern the recommendation/simulation endpoints should follow later.
- Verified beyond the plan's own curl example: also tested wrong extension (422), wrong `Content-Type` header (422), an oversized 11MB file (422, exact byte counts in the error), missing auth (401), and confirmed no orphaned files/directories are written to disk for any rejected upload (validation runs before any storage write).

#### Objective
Let an authenticated organization user upload a product concept (images, description, branding) for later simulation.

#### What to Develop
- Local file storage service (abstracted behind a small interface).
- Product schemas (create/response).
- `POST /api/v1/products` (multipart: image + JSON fields), `GET /api/v1/products`, `GET /api/v1/products/{id}`.

#### Files to Create
- `backend/app/services/storage_service.py`
- `backend/app/schemas/product.py`
- `backend/app/services/product_service.py`
- `backend/app/api/v1/products.py`

#### Files to Modify
- `backend/app/api/v1/router.py` — include the products router.
- `backend/app/core/config.py` — confirm `STORAGE_ROOT` is defined (added in Step 2).

#### Implementation Details
`storage_service.py` exposes `save_upload(file, subfolder) -> path` and `get_path(relative_path) -> Path`, backed by the local filesystem under `STORAGE_ROOT/products/{product_id}/`. The interface is intentionally minimal (two functions) so it can be swapped for object storage later without touching callers — no S3 integration is built now, since nothing in the current requirements needs it. Validate uploaded files: content-type must be an image MIME type, size capped (e.g. 10MB), extension whitelist (`.jpg`, `.jpeg`, `.png`) — this is a system boundary, so input is validated per project-wide security guidance. `product_service.create_product()` persists the row with `user_id` from `get_current_user`, ensuring users can only ever create products under their own account. `GET /products` and `GET /products/{id}` scope results to `current_user.id` unless the caller is an admin.

#### Dependencies
Step 10 (auth deps), Step 5/6 (Product model + migration).

#### Expected Result
An authenticated user can upload a product with an image and description; it's stored on disk and persisted in `products`; they can list and retrieve their own products but not another user's.

#### Verification
```
curl -X POST http://localhost:8000/api/v1/products \
  -H "Authorization: Bearer <token>" \
  -F "name=Test Sneaker" -F "description=..." -F "category=Footwear" \
  -F "image=@sample.jpg"
```
Returns 201 with product id; file appears under `backend/storage/products/<id>/`; `GET /products` for a second user's token does not show it.

#### Completion Criteria
Upload, list, and get-by-id work correctly; ownership scoping is enforced; invalid file types/sizes are rejected with a clear 4xx.

---

### Step 12 — Image Preprocessing Pipeline

#### When
Immediately after Step 11 — the GAN engine (Phase 6) needs a normalized input format, so preprocessing must exist before generation is wired up, but is independent enough to build right after upload.

#### Objective
Normalize uploaded product images into the fixed input format the GAN inference step (Step 16) expects.

#### What to Develop
Image preprocessing function: resize to the model's expected resolution, center-crop/pad to a fixed aspect ratio, normalize color channels, save the processed copy.

#### Files to Create
- `backend/app/services/image_preprocessing.py`

#### Files to Modify
- `backend/app/services/product_service.py` — call preprocessing after a successful upload, store the resulting path in `products.preprocessed_image_path`.

#### Implementation Details
Use `Pillow` for resize/crop (no need for a heavier image library at this stage). Fixed target size chosen to match the pretrained StyleGAN2 checkpoint's expected input (documented precisely in Step 15 once the checkpoint is selected — this step defines the function signature and pipeline slot; the exact resolution constant is set together with Step 15 so the two don't drift). Preprocessing runs synchronously at upload time (images are small; no need for a background job here).

**Status: ✅ Completed (2026-08-17).**

**Implementation notes / decisions made (implemented directly, per user's fast-track instruction):**
- Resolution constant set to **256×256 RGB**, defined once in `image_preprocessing.py` (`TARGET_SIZE`) and referenced from there when Step 15 loads the checkpoint, so the two stay in sync by construction rather than by convention.
- `ImageOps.fit()` (Pillow) does the resize + center-crop-to-target-aspect-ratio in one call; added `ImageOps.exif_transpose()` first to respect phone/camera orientation metadata (a real correctness issue `ImageOps.fit` alone wouldn't catch) — small, well-justified addition beyond the literal plan text.
- Verified with exactly the case the plan calls for (a non-square, oversized 1800×900 image) plus an additional RGBA-with-transparency PNG upload, to confirm the `.convert("RGB")` normalization actually handles a real alpha-channel image, not just same-mode inputs.

#### Dependencies
Step 11.

#### Expected Result
Every uploaded product has both its original and a preprocessed image on disk, with the preprocessed path recorded on the `Product` row.

#### Verification
Upload a non-square, oversized test image; confirm the preprocessed output file exists, has the expected fixed dimensions, and `products.preprocessed_image_path` is populated.

#### Completion Criteria
Preprocessing runs automatically on upload; output dimensions are deterministic and match what Step 15/16 will require.

---

## Phase 5 — Dataset Pipeline Ingestion

### Step 13 — Dataset Ingestion Script

#### When
After Phase 4. Independent of Phases 6–10's code, but must exist before Step 14 (persona seeding) and before Step 17 (GAN fine-tuning) can use real reference data.

**Status: ✅ Completed (2026-08-17).**

**Real problems found and fixed while implementing this step (not just writing code, actually running it against real state):**
1. **This step's own "fallback" text above was factually wrong.** It said to test against "the pipeline's existing 4-row test fixtures (`datasets/raw/sample_zappos.csv`, etc.)" — but those files are raw, pre-normalization *inputs* to Services 01/03/04/05 (Zappos/Amazon-native column names like `id,name,brand,department` and `asin,reviewText,overall`), not the pipeline's canonical *output* schema this script actually reads (`product_id,brand,model,...`, `review_id,product_id,review_text,rating,...`). Confirmed by inspecting both files directly, and confirmed `datasets/master/` and `datasets/versions/` are genuinely empty (only `.gitkeep`) — no real pipeline output exists anywhere in the repo yet. Fixed by: (a) verifying the script handles today's real state correctly — running it against the actual pipeline root reports 0 rows with a clear "file not found" note for all 5 tables, no crash; (b) building a synthetic fixture set matching the *real* output schemas (in the scratchpad, never written into the archived pipeline's own directories) to actually prove the ingestion logic works, since no real usable fixture exists to test against.
2. **Found and fixed a real, foundational bug in `core/config.py`**: `Settings`' `env_file=".env"` resolved relative to the process's *working directory*, not the file's own location — worked by accident for `uvicorn` (always run from `backend/`) but silently loaded the wrong `.env` (the root one, for `docker-compose.yml`) for this script and would break identically for `alembic` or any future script run from elsewhere. Fixed by resolving `_ENV_FILE`/`STORAGE_ROOT`'s default from `Path(__file__)` instead. Updated `backend/.env.example` and the local `backend/.env` to match (removed the now-redundant explicit `STORAGE_ROOT` line). Regression-checked `GET /health` afterward — no change in behavior for the normal `uvicorn` path.
3. **Found and fixed a real isolation bug in my own first draft of this script**: a schema-validation failure on one file (tested by deliberately dropping a required column from `market.csv`) aborted the *entire* script before reaching `product_intelligence.csv` — the four unrelated files shouldn't fail together. Wrapped each file's processing in its own try/except, so failures are isolated, reported clearly, and the script still exits non-zero overall (`raise SystemExit(1)` if any file failed) — scriptable for later automation, not just human-readable.

**Additional implementation notes:**
- Per-file path overrides added (`--master-products`, `--image-metadata`, `--reviews`, `--market`, `--product-intelligence`) beyond the plan's single `--pipeline-root` — the exact output locations for `reviews.csv`/`market.csv`/`product_intelligence.csv`/`image_metadata.csv` are genuinely unverified (nothing has ever generated them), so hardcoding one guessed path each felt riskier than making them overridable with a documented best-guess default.
- Verified end-to-end against synthetic fixtures: correct type coercion (float/int/bool/date/datetime), correct JSONB parsing (`image_refs`, `provenance` land as real Python list/dict, not strings), idempotent upsert (re-running with a changed price updates the existing row in place — same row count, new value, refreshed `ingested_at`/`source_dataset_version`), and the per-file failure isolation described above. Test data truncated from the tables afterward to leave a clean state.

#### Objective
Resolve Open Decision #11/Decision #12: give the core system a concrete, working way to pull the dataset-extraction pipeline's frozen outputs into its own database, on demand, as a batch job.

#### What to Develop
A standalone script that reads the pipeline's versioned output files and upserts them into the `ref_*` tables from Step 7.

#### Files to Create
- `scripts/ingest_dataset_pipeline.py`

#### Files to Modify
None (reads external files, writes via existing `backend/app` DB session).

#### Implementation Details
The script takes a `--pipeline-root` argument pointing at `Capstone Dataset (Archived)/Capstone Dataset/DryRunAI/` and reads:
- `datasets/master/master_products.csv` → `ref_products`
- the image metadata CSV referenced by the Asset Manager service output (`image_metadata.csv`) → `ref_images`
- `reviews.csv` → `ref_reviews`
- `market.csv` → `ref_market`
- `product_intelligence.csv` → `ref_product_intelligence`

For each, validate columns against the corresponding `schemas/*.json` contract (fail loudly on a mismatch rather than silently importing malformed data — this is exactly the kind of external-boundary validation the project's global instructions call for), then upsert by primary key (`product_id`/`review_id`/etc.), stamping `ingested_at` and `source_dataset_version` (from the pipeline's own catalog version folder name, e.g. `catalog_v1`). The script is idempotent — re-running it with the same source data updates existing rows rather than duplicating them.

**Fallback for development before the pipeline has real data**: since `project_manifest.json` currently shows all record counts at `0`, run this script against the pipeline's existing 4-row test fixtures (`datasets/raw/sample_zappos.csv`, etc., already present in the repo) to validate the ingestion logic end-to-end. Re-run it against real output once the pipeline team executes Services 01–07 for real — no code change needed, only re-pointing `--pipeline-root` at a populated `datasets/versions/...` directory.

#### Dependencies
Step 7 (ref tables exist). Reads, but does not modify, the archived dataset pipeline.

#### Expected Result
Running the script populates all five `ref_*` tables from whatever data currently exists in the pipeline's output directories (fixtures today, real data once the pipeline is run).

#### Verification
```
python scripts/ingest_dataset_pipeline.py --pipeline-root "../Capstone Dataset (Archived)/Capstone Dataset/DryRunAI"
```
Row counts in `ref_products`/`ref_reviews`/etc. match the source CSVs; re-running produces no duplicate rows (same row count, updated `ingested_at`).

#### Completion Criteria
Script runs cleanly against current fixtures, validates against the pipeline's schema contracts, is idempotent, and is documented as ready to re-run once real pipeline data exists.

---

### Step 14 — Persona-Template Seed Extraction

#### When
Immediately after Step 13.

#### Objective
Use real `ref_product_intelligence` target-segment fields (where available) to ground the curated persona library (Decision #4), instead of the 2–3 hand-picked examples in the source diagrams.

#### What to Develop
A seeding routine that derives candidate persona attribute distributions (age ranges, income segments, lifestyles, regions actually observed in `ref_product_intelligence`) and feeds them into the persona template list built in Step 19.

#### Files to Create
- `backend/scripts/seed_personas.py` (a second small script, separate from ingestion since it's about the application's own `personas` table, not a `ref_*` mirror)

#### Files to Modify
None yet — the actual `personas` table population happens in Step 19; this step only builds the extraction/derivation logic it will call.

#### Implementation Details
Query `ref_product_intelligence` for distinct, non-null `target_age_min/max`, `target_gender`, `target_income_segment`, `target_region`, `target_lifestyle` combinations. When the table is fixture-sized (per Step 13's current fallback), this yields little real variety — the function is written to degrade gracefully: if fewer than a configurable minimum number of distinct segments exist in `ref_product_intelligence`, fall back to a hand-authored baseline segment list so Step 19 always has ~20 usable templates regardless of how much real pipeline data exists yet. This keeps Phase 7 buildable and testable today, while automatically getting more grounded once the pipeline is populated for real.

#### Dependencies
Step 13.

**Status: ✅ Completed (2026-08-17).**

**Implementation notes / decisions made (implemented directly, per user's fast-track instruction):**
- `MIN_REAL_SEGMENTS = 15` threshold (below Step 19's ~20-template target, so a near-complete real dataset doesn't get needlessly discarded in favor of the baseline).
- `BASELINE_SEGMENTS` is a hand-authored list of exactly 20 structured `(age range, income segment, lifestyle, region)` combinations, covering every named example from the source diagrams (price-sensitive student, urban professional, trend-driven buyer, budget shopper, premium user) plus systematic expansion — not an arbitrary/random list.
- No formal pytest file added yet — verified with an ad-hoc script directly against real Postgres, consistent with every step so far; the formal automated suite is Step 38's job. Test data truncated afterward.
- Verified all three cases: empty table (today's real state) → baseline; the plan's own exact scenario (a 4-row fixture) → still baseline; 20 distinct real segments → switches to real data, confirming the threshold logic in both directions, not just the empty-table case.

#### Expected Result
A callable function/module that returns a list of segment dicts, sourced from real data when available and from a documented fallback baseline otherwise.

#### Verification
Unit test against a `ref_product_intelligence` fixture with 4 rows confirms the fallback baseline activates; a test with 20+ distinct synthetic segments confirms real data is used instead.

#### Completion Criteria
Extraction logic works correctly in both the current (fixture-scale) and eventual (real-scale) data conditions; behavior at each is explicit and tested, not accidental.

---

## Phase 6 — GAN Product Generation Engine

### Step 15 — GAN Model Integration (Pretrained Checkpoint)

#### When
After Phase 4 (needs preprocessed product images) and independent of Phase 5. Can be developed in parallel with Phases 5, 7–10 once Phase 4 is done.

#### Objective
Load a pretrained StyleGAN2 checkpoint and confirm inference runs end-to-end, before building the controllable-variation logic on top of it — satisfies the "Planned" GAN component from PRD §14 becoming real.

**Status: ✅ Completed (2026-08-17).**

**This was the highest-risk step in the whole plan, and it required real judgment calls — documented in full:**

1. **Environment check before writing any code**: this machine has an NVIDIA GPU (RTX 4050, 6GB VRAM, driver supports CUDA 13.1) but **no CUDA toolkit (`nvcc`) or MSVC compiler**. Genuine StyleGAN2 implementations rely on compiling custom CUDA kernels for their fastest path. I flagged this to the user with three options (pure-PyTorch alternative architecture / attempt real StyleGAN2 anyway / install a full compiler toolchain first) rather than silently picking one, since it directly affects Decision #5 (the plan's own resolved "StyleGAN2" choice) and carried real risk of losing hours to environment issues.
2. **User chose to attempt real StyleGAN2 anyway.** Before writing code, verified via the actual NVIDIA source (`torch_utils/ops/bias_act.py`, `upfirdn2d.py`) that both custom ops have genuine, automatic pure-PyTorch fallbacks when compilation fails (a warning, not a crash) — this de-risked the attempt substantially and justified proceeding.
3. **"Pip-installable" (as the plan's Implementation Details literally says) turned out not to be accurate for any real StyleGAN2 implementation** — NVIDIA's official `stylegan2-ada-pytorch` is a research repo (clone-and-run), not a PyPI package. Resolved by vendoring only the minimal inference-required subset (`dnnlib/`, `torch_utils/`, `legacy.py` — 390KB, no training/loss/augmentation code) into `backend/app/ml/gan/vendor/stylegan2_ada/`, rather than pip-installing a lower-quality alternative just to satisfy the letter of "pip install."
4. **Checkpoint domain**: used NVIDIA's official **AFHQ-cat** pretrained checkpoint (512×512), not a footwear/product checkpoint — none exists publicly. Chosen over FFHQ (faces, 1024×1024) for the smaller VRAM footprint and being marginally closer to "object/creature" than human faces. Domain mismatch is expected and explicitly deferred to Step 17's fine-tuning (per the user's own "training can be done later" instruction) — this step's actual job (checkpoint loads, forward pass produces a valid image) is fully satisfied regardless of domain.
5. **License**: NVIDIA Source Code License — **non-commercial research/evaluation use only**. Fine for this academic capstone; flagging clearly since it would need revisiting before any commercial productization (relevant given PRD §36's SaaS future-scope mention).
6. **Found and fixed real noise, not just correctness, issues**: NVIDIA's fallback path prints/warns on every single forward pass (not just once), which would spam server logs heavily once Step 16 generates multiple variants per simulation. Added a targeted `warnings.filterwarnings` for the expected warning plus a narrow `contextlib.redirect_stdout` wrapper around the generation call (not a blanket suppression) so genuine errors still surface normally.
7. **Native resolution (512×512) resized down to Step 12's fixed 256×256`TARGET_SIZE`** via `F.interpolate` as the final step of `generate_image()`, imported directly from `image_preprocessing.py` so the two constants can never drift apart.

#### What to Develop
A thin model-loading wrapper around a pretrained StyleGAN2 implementation.

#### Files to Create
- `backend/app/ml/__init__.py`
- `backend/app/ml/gan/__init__.py`
- `backend/app/ml/gan/model.py`

#### Files to Modify
- `backend/requirements.txt` — add `torch`, `torchvision`, a StyleGAN2 PyTorch implementation package, `torchmetrics` (used in Step 18).

#### Implementation Details
`model.py` exposes `load_generator(checkpoint_path) -> Generator` and fixes the exact input/output resolution constant referenced back in Step 12 (e.g., 256×256, matching the checkpoint used). Use an existing, pip-installable pretrained StyleGAN2 checkpoint appropriate for product/object imagery (general-object or fashion-domain pretrained weights, publicly licensed — consistent with the public-data-only constraint, PRD §5.6/§35). Store checkpoint files under `backend/storage/models/` (gitignored, per Step 1). Document the exact checkpoint source/license in a short comment at the top of `model.py` so provenance is traceable, matching the same public-data discipline the dataset pipeline itself follows.

#### Dependencies
Step 12 (fixed preprocessing resolution must match this step's checkpoint).

#### Expected Result
The generator loads successfully and can run a forward pass producing a valid image tensor from a random latent vector.

#### Verification
A small script/test loads the checkpoint and generates one image from a random seed; output is a valid image (correct shape, no NaNs) and is saved to disk for manual visual sanity-check.

#### Completion Criteria
Checkpoint loads reliably, a single forward pass produces a plausible image, resolution matches Step 12's preprocessing output.

---

### Step 16 — Latent-Space Attribute Variation & Variant Generation

#### When
Immediately after Step 15.

#### Objective
Produce the "N product design variants" FR#4 calls for (PRD §9), controllably varying the attributes named in the PRD (color, texture, layout, branding presentation).

**Status: ✅ Completed (2026-08-17).**

**Implementation notes / decisions made (implemented directly, per user's fast-track instruction):**
- **Base-image-conditioned GAN inversion, explicitly named in this step's own Implementation Details, was deliberately not implemented.** The plan's text anticipated a pretrained (not from-scratch) checkpoint and pre-authorized "documented, coarser controls" when clean disentangled directions aren't available — but the specific checkpoint in use (Step 15's AFHQ-cat) makes projecting an actual uploaded *product photo* into its latent space worse than just coarse: it would converge toward a meaningless "closest cat" approximation, not a useful starting point, while adding real optimizer latency for no benefit. Documented this reasoning in full at the top of `inference.py` rather than silently skipping it. Each product instead gets a deterministic per-product anchor seed (hash of `product_id`), so results are still reproducible per product without inversion.
- **Genuine nearby latent-space perturbation, not just distinct random seeds**: extended `model.py` with `generate_image_from_latent()` (accepts a raw latent tensor) and `random_latent()`, refactoring `generate_image()` into a thin wrapper — this lets `inference.py` compute a shared anchor latent plus small (`radius=0.4`) offsets per variant, which is mathematically a real "nearby perturbation" (confirmed visually: variants share a recognizably similar cat pose/structure, not four unrelated animals).
- **Color control is real and works precisely**: HSV hue-shift post-processing, verified by generating 4 variants at hue 0°/90°/180°/270° and visually confirming the exact expected color-wheel progression (orange → green → blue → pink) on the same underlying cat.
- **`branding_style` has no real backing** — documented plainly in both the module docstring and each variant's `attributes.note` field rather than inventing a fake mechanism to look more complete than it is.
- Extended `storage_service.py` with `save_pil_image()` (parallel to the existing `save_upload()` for `UploadFile`s) since GAN output is an in-memory `PIL.Image`, not an uploaded file — small, consistent addition, not in the step's literal file list.
- Verified against real DB rows (no API exists yet for creating a Simulation — that's Steps 27–28 — so test `User`/`Product`/`Simulation` rows were inserted directly for this step's verification): `generate_variants_for_simulation()` with `n=4` produced 4 distinct `product_variants` rows and 4 distinct image files in ~4 seconds on the GPU; **viewed all 4 images directly**, not just checked file sizes/shapes, to confirm they're genuinely different pictures, not duplicates with different metadata.

#### What to Develop
An inference function that takes a product's preprocessed image plus a requested variant count, and returns N generated variant images with recorded attribute metadata.

#### Files to Create
- `backend/app/ml/gan/inference.py`

#### Files to Modify
- `backend/app/services/product_service.py` — none required here; a new `gan_service.py` (below) is the caller-facing entry point, kept separate from the raw `ml/gan` module per the project's existing services/ml layering.
- `backend/app/services/gan_service.py` (new)

#### Implementation Details
`inference.py`'s `generate_variants(base_image, n, attribute_ranges) -> list[VariantResult]` projects the input image into the generator's latent space (via an off-the-shelf encoder/optimization-based projection, since this is a pretrained, not from-scratch-trained, checkpoint per Decision #6), then samples `n` nearby latent-space perturbations constrained to vary specific attribute directions (color/texture/layout/branding) rather than unconstrained random sampling — this is what "controlled" generation means per PRD §3/§16. Where the pretrained checkpoint doesn't expose clean disentangled attribute directions out of the box, fall back to documented, coarser controls (e.g., color-channel post-processing + latent interpolation for layout/texture) and record this limitation directly in code comments — do not silently claim finer control than the model actually provides. `gan_service.py` wraps this for the rest of the app: `generate_variants_for_simulation(simulation_id, n) -> list[ProductVariant]`, persisting each result as a `ProductVariant` row with `attributes` JSON and `image_path`.

#### Dependencies
Step 15.

#### Expected Result
Given a product and a simulation, the system produces N distinct `ProductVariant` rows with generated images and recorded (even if coarse) attribute metadata.

#### Verification
Call `gan_service.generate_variants_for_simulation()` against a test product/simulation with `n=4`; confirm 4 distinct image files and 4 `product_variants` rows exist, with visibly different (not identical) output images.

#### Completion Criteria
Variant generation is callable as a service function, produces the requested count, persists correctly, and variants are visibly distinct from one another.

---

### Step 17 — GAN Fine-Tuning Pipeline

#### When
After Step 16, and functionally blocked on real ingested image data (Step 13) for anything beyond a smoke test.

#### Objective
Improve output realism/domain-relevance beyond the generic pretrained checkpoint by fine-tuning on real product images, resolving Decision #6 (transfer learning, cloud GPU).

**Status: ✅ Completed (2026-08-17) — as a smoke test only, exactly as this step's own text scopes it.** Per the user's explicit instruction that training/output quality is deferred, this step wrote the real fine-tuning script but did not attempt any meaningful training run.

**Implementation notes / decisions made (implemented directly, per user's fast-track instruction):**
- **Simplified training loop, not NVIDIA's full recipe** — documented prominently in the module docstring: standard non-saturating GAN loss (G/D alternating Adam updates), no R1 gradient penalty, no path-length regularization, no ADA augmentation pipeline. Reproducing those would require vendoring substantially more of NVIDIA's training infrastructure than Step 15's inference-only subset — out of scope for what this step actually needs to prove. EMA sync is a direct weight copy, not NVIDIA's running-average schedule, for the same reason.
- **Same fixture problem as Step 13, hit again**: the pipeline's raw fixtures contain no actual image files (only metadata CSV rows), so there was nothing real to smoke-test against. Used 6 small synthetic placeholder images (solid colors) instead, clearly not claiming they're real product data.
- **Verified for real, not just written**: ran 5 actual G/D training steps (batch size 2) against the synthetic images on the local GPU — completed without error, with sane loss values printed per step. Confirmed the output `.pkl` has a different SHA-256 hash than the input (the plan's literal completion criteria), and — beyond what the plan asked for — confirmed the fine-tuned checkpoint still loads correctly through Step 15's existing `model.py` and produces valid output, proving the re-saved pickle format wasn't broken.
- Local hardware (RTX 4050, no compiler) handled 5 steps at 512×512/batch=2 without OOM, but slowly (pure-Python op fallback, same as Steps 15–16) — consistent with, not contradicting, this step's own instruction to use a cloud GPU for any real fine-tuning run.

#### What to Develop
A standalone fine-tuning script (not part of the request/response path — this runs offline, ahead of time).

#### Files to Create
- `backend/app/ml/gan/finetune.py`

#### Files to Modify
None (offline script).

#### Implementation Details
`finetune.py` is a CLI script: loads the Step 15 checkpoint as initialization, continues training on the image corpus ingested via `ref_images`' downloaded files (once Step 13 has run against real pipeline output), for a small number of epochs appropriate for a modest, curated dataset. Explicitly documented to be run on a cloud/rented GPU (Colab/Kaggle notebook or equivalent), not the certified local machine — this reconciles PRD §21/§28's flagged hardware tension. **This step cannot produce a meaningfully improved checkpoint until the dataset pipeline has been run for real** (currently zero records) — until then, it is validated only as a smoke test against the pipeline's 4-row fixtures (confirming the training loop runs without error, not that it produces a better model). Record this precondition directly in the script's `--help` text and in a top-of-file comment.

#### Dependencies
Step 15, Step 13 (for meaningful data; fixtures suffice for a smoke test).

#### Expected Result
A fine-tuning run completes without error and produces an updated checkpoint file; quality improvement is only meaningfully assessable once real data exists.

#### Verification
Run the script against fixture data for a handful of steps; confirm it completes without crashing and writes a new checkpoint file with a different file hash than the input.

#### Completion Criteria
Script runs end-to-end against available data today (fixtures); documented and ready to re-run against real data once the external pipeline prerequisite is satisfied. Not blocking for the rest of Phase 6/7 — Step 16 works against the pretrained checkpoint regardless.

---

### Step 18 — Realism & Diversity Evaluation (FID)

#### When
After Step 16 (needs generated variants to score).

#### Objective
Close Open Decision #5's realism-metric gap: give generated variants an objective, standard realism score.

**Status: ✅ Completed (2026-08-17).**

**Implementation notes / decisions made (implemented directly, per user's fast-track instruction):**
- **FID is computed once per generation batch, not per variant** — all N variants from one `generate_variants_for_simulation()` call share a single `fid_score`. This is a deliberate, documented design choice, not a shortcut: FID is mathematically a set-vs-set statistic (fits a Gaussian to each set's InceptionV3 features), so "one variant's own FID" isn't a meaningful concept. Stated plainly in `evaluation.py`'s docstring.
- Added `torch-fidelity` to `requirements.txt` — required by `torchmetrics`'s FID implementation at runtime, not documented in the plan text (which only names `torchmetrics`).
- **Real bug found and fixed during integration**: `torch.stack()` failed the first time this ran against a real product, because the unprocessed original upload (its native resolution) and the 256×256 preprocessed/generated images aren't the same shape. Fixed by resizing every image to `TARGET_SIZE` before stacking, reusing the same constant Steps 12/15/16 already share.
- `compute_fid()` returns `None` (not a misleading NaN/Inf) when the sample is too degenerate (fewer than 2 images in either set) for FID's covariance estimate to mean anything — this is the "documented limitation" the plan's completion criteria calls for, enforced in code rather than left as a comment only.
- Verified both required cases directly: (1) end-to-end against a real uploaded product — 4 variants, all with the same non-null, finite `fid_score` persisted in the DB; (2) the plan's explicit degraded-vs-normal comparison — a deliberately noise-corrupted batch scored **409 vs. 131** for a normal batch, confirming FID is correctly oriented (higher = worse) and meaningfully discriminating even at this small sample size, not just returning a number.

#### What to Develop
FID (Fréchet Inception Distance) computation between a reference image set and generated variants.

#### Files to Create
- `backend/app/ml/gan/evaluation.py`

#### Files to Modify
- `backend/app/services/gan_service.py` — after generation, compute and persist `fid_score` on each `ProductVariant`.

#### Implementation Details
Use `torchmetrics.image.fid.FrechetInceptionDistance`, comparing generated variants against the product's own reference image(s) (and, once available, against `ref_images` real product photos for the same category) as the "real" distribution. FID requires a reasonably sized sample to be statistically meaningful — document this limitation clearly (a single-product, small-N comparison is a rough signal, not a rigorous benchmark) rather than overstating what a small-sample FID means.

#### Dependencies
Step 16.

#### Expected Result
Every generated `ProductVariant` has a `fid_score` recorded, usable later for filtering/ranking (Phase 12) and for surfacing in the dashboard (Phase 13).

#### Verification
Generate variants for a test product; confirm each has a non-null `fid_score`; confirm a deliberately degraded/noisy generation run produces a visibly worse (higher) FID than a normal run.

#### Completion Criteria
FID computed and persisted per variant; documented limitation of small-sample FID is stated in code comments and will be carried into Section 8 (Testing Plan) as a known caveat, not silently hidden.

---

## Phase 7 — Persona & LLM Simulation Engine

### Step 19 — Persona Template Library & Seeding

#### When
After Step 14 (needs the segment-extraction logic) and independent of Phase 6 — can be built in parallel with Steps 15–18.

#### Objective
Build and seed the ~20-template curated persona library that resolves Decision #4.

**Status: ✅ Completed (2026-08-17).**

**Implementation notes / decisions made (implemented directly, per user's fast-track instruction):**
- `template_key`/`name`/`prompt_template`/`behavior_traits` are derived from each segment's `lifestyle` via a lookup table (`_BEHAVIOR_BY_LIFESTYLE`) covering the 8 lifestyle categories used in Step 14's baseline list, with a generic fallback behavior description for any `lifestyle` string not in that lookup — needed because real `ref_product_intelligence.target_lifestyle` values (once real data exists) aren't constrained to this controlled vocabulary, and this was verified directly (see below), not just assumed safe.
- Seeding is idempotent via Postgres `ON CONFLICT (template_key) DO UPDATE`, matching the ingestion script's pattern from Step 13 — re-running after a baseline-list edit updates existing rows rather than duplicating them.
- Real-segment `template_key`s get a short content-hash suffix appended, since two real segments could otherwise slugify to the same key (e.g. identical age/region with only a differing, unpredictable `lifestyle` string) — the baseline list doesn't need this since its combinations are hand-verified unique.
- Verified all of: 20 rows seeded from the baseline list with 20 distinct `template_key`s; prompt/behavior content spot-checked against PRD Sec15's exact structure; re-running the script twice leaves the count at 20 (idempotent, not duplicated); and the real-segment path specifically, with 16 synthetic segments using an *unrecognized* lifestyle string, confirmed both the source switch (baseline -> real) and the default-behavior fallback engage correctly, not just the already-covered lifestyle names.

#### What to Develop
- The concrete list of persona templates (hand-authored baseline + real-data-derived, per Step 14).
- A seeding script/migration data loader that inserts them into `personas`.

#### Files to Create
- `backend/app/ml/llm/__init__.py` — package init only here; provider code lands in Step 20.
- `backend/scripts/seed_personas.py` — extends Step 14's script to actually write `Persona` rows (Step 14 built the extraction logic; this step consumes it).

#### Files to Modify
None beyond the script above.

#### Implementation Details
Baseline templates include (at minimum) the concrete examples named across the source diagrams — "Price-sensitive student," "Urban professional," "Trend-driven buyer," "Budget shopper," "Premium user" — expanded to ~20 by combining the documented attribute dimensions (age range × income segment × lifestyle × region) systematically rather than picking 20 arbitrarily, so the library has structured, explainable coverage. Each template gets a `prompt_template` field following the example structure PRD §15 already gives ("Persona: {trait}; Income: {level}; Preference: {pref}; Behavior: {behavior}") — this becomes the seed for Step 20/21's LLM prompt construction. `source="seeded"` on every row from this step (reserved `"dynamic"` value is for Phase 17).

#### Dependencies
Step 14.

#### Expected Result
`personas` table contains ~20 distinct, well-differentiated persona rows after running the seed script.

#### Verification
`SELECT count(*) FROM personas;` returns ~20; spot-check a handful of rows for distinct, non-overlapping attribute combinations.

#### Completion Criteria
Persona library is seeded, structured (not arbitrary), and grounded in real segment data where Step 14 found enough of it.

---

### Step 20 — LLM Provider Abstraction & Prompt Engine

#### When
Immediately after Step 19.

#### Objective
Give the persona-reaction step (Step 21) a pluggable LLM backend — the SRS explicitly permits either an API or an open-source model (PRD §14, PROJECT_CONTEXT.md's explicit note that this project allows external LLM API usage) — without hardcoding one vendor.

**Status: ⚠️ Completed with one verification gap — documented honestly below, not glossed over.**

**Implementation notes / decisions made (implemented directly, per user's fast-track instruction):**
- Concrete provider: Anthropic (`anthropic` SDK), selected via `LLM_PROVIDER` (currently the only implemented option, matching the plan's own example) — `ANTHROPIC_API_KEY`/`ANTHROPIC_MODEL` added to `Settings` and `.env.example`, read from environment only.
- `prompt_templates.py` includes both prompt construction **and** response parsing (`parse_persona_reaction`) — not split from Step 21 — since the parsing logic is tightly coupled to the exact JSON schema the prompt itself demands; keeping them together avoids the schema being defined in one file and consumed in another with no shared source of truth. Handles a real, common LLM habit (wrapping JSON in a markdown code fence despite being told not to) rather than treating it as a hard failure, and clamps out-of-range `purchase_likelihood` values rather than silently accepting bad data.
- **Verification gap, disclosed rather than hidden**: the plan requires both a mocked-provider check *and* "a manual, real call against the configured provider" for full completion. I asked whether to add a real `ANTHROPIC_API_KEY`, and the user chose to skip real verification for now. **The mocked-provider path is fully verified** (prompt construction with real persona/scenario data; response parsing for clean JSON, markdown-fenced JSON, out-of-range clamping, and malformed input all confirmed correct; the "no API key configured" error path also confirmed to fail clearly rather than silently). **The real end-to-end API call has not been performed** — `get_llm_provider().complete()` against the live Anthropic API is unverified. This should be done before relying on Step 21+ in a live demo; add `ANTHROPIC_API_KEY` to `backend/.env` and re-verify whenever convenient.

#### What to Develop
An abstract `LLMProvider` interface with at least one concrete implementation, selected via configuration.

#### Files to Create
- `backend/app/ml/llm/provider.py`
- `backend/app/ml/llm/prompt_templates.py`

#### Files to Modify
- `backend/app/core/config.py` — add `LLM_PROVIDER` (e.g. `"anthropic"`) and the corresponding API-key setting (e.g. `ANTHROPIC_API_KEY`), read from environment only, never hardcoded (per project-wide secrets policy).
- `backend/.env.example` — document the new variable(s).
- `backend/requirements.txt` — add the chosen provider's SDK.

#### Implementation Details
`provider.py` defines `class LLMProvider(Protocol): def complete(self, prompt: str) -> str`, plus a `get_llm_provider() -> LLMProvider` factory reading `settings.LLM_PROVIDER` and instantiating the matching concrete class. Ship one working concrete implementation (e.g. an Anthropic-backed provider using the API key from settings) so the system is runnable end-to-end; the `Protocol`-based interface means swapping to a different API or a local open-source model later is a config change plus one new small class, not a rewrite. `prompt_templates.py` builds the full persona-reaction prompt from a `Persona.prompt_template`, the `ProductVariant.attributes`, and the `Simulation`'s scenario fields (pricing/demographic/messaging), instructing the model to return structured output (qualitative reaction text + purchase-likelihood estimate) in a parseable format (e.g., a small JSON object).

#### Dependencies
Step 19 (needs `Persona.prompt_template` to build on).

#### Expected Result
`get_llm_provider().complete(prompt)` returns a real model completion when a valid API key is configured.

#### Verification
Unit test with a mocked provider (no real API call) confirms prompt construction is correct; a manual, real call against the configured provider (using a real API key set locally, never committed) confirms end-to-end connectivity.

#### Completion Criteria
Interface is provider-agnostic; at least one real provider works when configured; no API key appears anywhere in source control.

---

### Step 21 — Persona-Reaction Simulation Service

#### When
Immediately after Step 20, and after Step 16 (needs real `ProductVariant`s to react to).

#### Objective
Implement FR#5 (PRD §9): "Product variants, predefined personas → LLM-based persona reasoning → Simulated customer feedback."

**Status: ⚠️ Completed with the same disclosed verification gap as Step 20.**

**Implementation notes / decisions made (implemented directly, per user's fast-track instruction):**
- Error marker for failed/unconfigured LLM calls is a prefixed string (`[LLM_ERROR] ...`) directly in `qualitative_text`, not a reuse of `risk_flags` — `risk_flags` is reserved for Step 24's actual risk-detection output; borrowing it for infrastructure errors would muddy that field's future meaning. `purchase_likelihood` defaults to `0.0` for error rows (a conservative, clearly-wrong-if-uninspected value, not left null against the model's non-nullable constraint).
- `iteration_number` defaults to `0` via a keyword argument — Step 26 (iteration loop) is what will actually drive this value across repeated calls; not yet wired to anything real.
- **Verified everything that doesn't require a real LLM response**: ran the real service against a real product/simulation with 3 personas × 4 variants — got exactly 12 `Feedback` rows (correct cross-product, no duplicates/gaps, confirmed directly in the DB), `sentiment_label` correctly still `NULL` on all of them (Step 23's job, not this one's), and **crucially, all 12 LLM calls failed (no API key configured) without aborting the simulation** — each was caught, logged, and recorded with the `[LLM_ERROR]` marker individually. This is a genuine, meaningful test of the per-pair failure-isolation design the plan requires, not a skipped check.
- **Not verified** (same gap as Step 20, now surfacing here as predicted): "qualitative_text varies meaningfully across different personas reacting to the same variant" — this requires real LLM responses, which requires `ANTHROPIC_API_KEY`. All 12 rows currently contain the same generic error text, not differentiated persona reasoning. Re-run this step's verification once a key is configured.

#### What to Develop
A service that, for a given simulation, runs every assigned persona against every generated variant and produces a `Feedback` row per pair.

#### Files to Create
- `backend/app/services/persona_service.py`

#### Files to Modify
None beyond the new file.

#### Implementation Details
`persona_service.simulate_persona_reactions(simulation_id) -> list[Feedback]`: for each `(persona, variant)` pair (from `simulation_personas` × the simulation's generated `product_variants`), build the prompt (Step 20), call the LLM provider, parse the structured response into `qualitative_text` and `purchase_likelihood`, and insert a `Feedback` row (leaving `sentiment_label`/`sentiment_score`/`engagement_score`/`risk_flags` null for now — those are populated by Phases 8–9, kept as separate concerns per the certified architecture's own layering: LLM Persona Layer is distinct from downstream analysis). Handle and log LLM call failures per-pair without failing the whole simulation (one bad persona/variant call shouldn't abort the run) — record a `Feedback` row with an error marker instead of silently dropping it.

#### Dependencies
Step 20, Step 16.

#### Expected Result
Running this service for a simulation with, say, 3 personas and 4 variants produces 12 `Feedback` rows with real qualitative text and purchase-likelihood values.

#### Verification
Run against a test simulation with a small persona/variant count; confirm the expected row count and that `qualitative_text` varies meaningfully across different personas reacting to the same variant (a price-sensitive persona should mention price; a premium persona should not react the same way).

#### Completion Criteria
Every persona×variant pair produces a `Feedback` row; failures are isolated and logged, not silently lost or simulation-halting.

---

### Step 22 — Persona-Response Consistency Check

#### When
Immediately after Step 21.

#### Objective
Close the other half of Open Decision #5's evaluation gap: measure whether a persona's reaction is stable/reliable, not just present.

**Status: ✅ Completed and fully verified (2026-08-17)** — this step's own required verification uses mocked providers explicitly, so it wasn't affected by the missing `ANTHROPIC_API_KEY` gap from Steps 20-21.

**Implementation notes / decisions made (implemented directly, per user's fast-track instruction):**
- "Simple sentiment-score proxy" (the plan's own words) is a small keyword-based polarity heuristic (`_crude_sentiment_proxy`) — explicitly *not* real sentiment analysis (that's Step 23's actual NLP model), and documented in code as such. It exists only to give `check_consistency` a second, cheap signal alongside `purchase_likelihood` drift.
- `consistency_variance` is the mean of the purchase-likelihood delta and the sentiment-proxy delta between the original and re-run response — a single number combining both signals, kept simple rather than storing two separate deltas.
- When no LLM provider is configured, the function returns early and leaves `consistency_variance` `NULL` rather than fabricating a number — consistent with how Step 21 handles the same missing-key condition, just without needing per-row error markers here since there's no Feedback row being newly created.
- **Verified exactly as the plan specifies, with both required mock scenarios**: seeded 8 real `Feedback` rows with a known baseline (`"Pretty good, I like it."`, `purchase_likelihood=0.5`). A deterministic mock (returns the identical response every time) produced `consistency_variance = 0.0` on all 4 sampled rows, with the other 4 correctly left `NULL`. An unstable mock (random text/likelihood each call) produced a mean variance of **1.17** on the same setup — a clear, large, correctly-oriented difference proving the mechanism actually detects inconsistency, not just that it runs.

#### What to Develop
A function that re-runs a sample of persona×variant pairs and computes output variance.

#### Files to Create
None — extends `persona_service.py`.

#### Files to Modify
- `backend/app/services/persona_service.py` — add `check_consistency(simulation_id, sample_rate) -> None`, populating `Feedback.consistency_variance`.

#### Implementation Details
For a configurable sample of the pairs processed in Step 21 (not all — repeating every call would double LLM cost/latency for marginal signal), re-run the same prompt, compare `purchase_likelihood` and a simple sentiment-score proxy between the two runs, and store the absolute difference as `consistency_variance` on the original `Feedback` row. This is a lightweight reliability signal, not a rigorous statistical framework — documented as such, consistent with how Step 18 documents FID's limitations.

#### Dependencies
Step 21.

#### Expected Result
A sampled subset of `Feedback` rows have a non-null `consistency_variance`, usable later to flag low-reliability results in the dashboard (Phase 13).

#### Verification
Run against a test simulation; confirm sampled rows get a `consistency_variance` value and unsampled rows remain null; a deliberately unstable mock provider (returns random values) produces visibly higher variance than a deterministic mock.

#### Completion Criteria
Consistency check runs on a configurable sample without materially increasing cost/latency of the full simulation; results are persisted and distinguishable from unsampled rows.

---

## Phase 8 — Sentiment Analysis

### Step 23 — NLP Sentiment Classification Service

#### When
After Step 21 (needs `Feedback.qualitative_text` to classify). Independent of Phase 6/9/10 — can run in parallel with those once Phase 7 exists.

#### Objective
Implement FR#6 (PRD §9): "Persona feedback text → NLP sentiment classification → Sentiment scores/labels (pos/neg/neutral)."

**Status: ✅ Completed and fully verified (2026-08-17)** — no external API dependency, so unaffected by the Steps 20-21 API-key gap.

**Implementation notes / decisions made (implemented directly, per user's fast-track instruction):**
- Model: `cardiffnlp/twitter-roberta-base-sentiment-latest` (RoBERTa-base, MIT-licensed) — chosen specifically because it natively outputs 3 classes (negative/neutral/positive) matching `SentimentLabel` exactly, rather than a 2-class model (e.g. SST-2 DistilBERT) that would need a threshold-based "derive neutral from confidence" workaround. Verified empirically (not assumed) that its label strings match the enum's values directly before writing the mapping.
- `sentiment_score` is signed: `+confidence` for positive, `-confidence` for negative, `0.0` for neutral (which has no natural sign) — makes downstream aggregation (Steps 25, 30) able to average scores meaningfully rather than needing to separately track label and magnitude.
- Verified with 4 real cases through the actual DB-backed service, not just the raw classifier: a clearly positive text (0.988 confidence, correct), a clearly negative text (-0.957, correct), a plain neutral statement ("It is a shoe.", correctly neutral), and — a case the plan didn't anticipate but is realistic given Steps 20-21's disclosed gap — the literal `[LLM_ERROR] ...` marker text, which classified as neutral without crashing, confirming the classifier handles non-natural-language input gracefully rather than only being tested on ideal inputs.

#### What to Develop
A sentiment classification wrapper and a service that applies it to `Feedback` rows.

#### Files to Create
- `backend/app/ml/nlp/__init__.py`
- `backend/app/ml/nlp/sentiment.py`
- `backend/app/services/sentiment_service.py`

#### Files to Modify
- `backend/requirements.txt` — add `transformers` (and `torch`, already present from Phase 6).

#### Implementation Details
`ml/nlp/sentiment.py` wraps a pretrained `transformers` sentiment pipeline (a standard, small, publicly licensed sentiment model — no model needs to be trained here, satisfying "no model named" in PRD §14 by picking a concrete, documented one). `sentiment_service.classify_feedback(simulation_id)` loads all `Feedback` rows for the simulation still missing a `sentiment_label`, runs classification on `qualitative_text`, maps the model's raw output to the project's `positive/negative/neutral` enum plus a numeric `sentiment_score`, and updates the rows.

#### Dependencies
Step 21.

#### Expected Result
Every `Feedback` row for a simulation has a populated `sentiment_label` and `sentiment_score` consistent with its `qualitative_text`.

#### Verification
Feed a hand-written clearly-positive and clearly-negative feedback string through the service directly; confirm correct label assignment. Run against a real simulation's feedback and spot-check a few rows for label/text agreement.

#### Completion Criteria
All feedback rows get classified; classification is directionally correct on obvious positive/negative test cases.

---

## Phase 9 — Risk Detection

### Step 24 — Rule-Based Risk Detection Engine

#### When
After Step 23 (needs sentiment scores as an input signal). Independent of Phase 6/10.

#### Objective
Implement FR#7 (PRD §9): "Sentiment + simulation results → Pattern/anomaly detection, rule-based + AI → Risk alerts/insights."

**Status: ✅ Completed and fully verified (2026-08-17)** — pure rule-based logic over existing DB data, no external dependency.

**Implementation notes / decisions made (implemented directly, per user's fast-track instruction):**
- **Corrected a real error in this step's own plan text**: it describes flagging "an unusually LOW fid_score" as indicating an unrealistic variant — backwards from how FID works, and directly contradicted by what Step 18 itself verified (a degraded/less-realistic batch scored HIGHER: 409 vs. 131 for normal). Implemented the correct direction (flag unusually *high* FID) and documented the correction prominently in the module docstring rather than silently fixing it.
- **`risk_flags` denormalized across every `Feedback` row for a variant**, not stored on a dedicated variant-level field — `ProductVariant` has no `risk_flags` column in the current schema, and adding one is outside this step's own file list (`services/risk_service.py` only, no migration). A disclosed, schema-driven choice.
- Four rules implemented exactly as specified: negative-sentiment ratio, average purchase-likelihood, average consistency-variance (Step 22), and FID (Step 18, direction corrected) — each threshold a named constant with a comment, not a magic number.
- **Verified exactly per the plan's own instructions, in one simulation with two variants**: a deliberately "risky" variant (75% negative sentiment, 0.10 avg purchase likelihood, 0.70 avg consistency variance, FID 450) triggered **all four rules** with clear, specific explanations; a deliberately "healthy" variant (100% positive, 0.85 avg likelihood, 0.05 variance, FID 95) triggered **zero** false-positive flags in the same run. Confirmed both the returned summary and the persisted `Feedback.risk_flags` in the database agree.

#### What to Develop
A rule-based risk scorer that flags simulations/variants with concerning patterns.

#### Files to Create
- `backend/app/services/risk_service.py`

#### Files to Modify
None beyond the new file.

#### Implementation Details
`risk_service.detect_risks(simulation_id)` evaluates, per variant, a small set of explicit, documented rules against its aggregated `Feedback` rows: e.g., negative-sentiment ratio above a threshold, average `purchase_likelihood` below a threshold, high `consistency_variance` (from Step 22, indicating unreliable persona signal), or an unusually low `fid_score` (from Step 18, indicating a possibly unrealistic variant). Each triggered rule appends a structured entry (`{rule, severity, detail}`) to that variant's relevant `Feedback.risk_flags` and/or a simulation-level risk summary. Rules are threshold-based and rule-based only, per PRD's own wording ("rule-based + AI insights") — no anomaly-detection model is trained; thresholds are configurable constants, not hardcoded magic numbers scattered through the function.

#### Dependencies
Step 23, Step 18, Step 22.

#### Expected Result
Simulations/variants with genuinely poor signals (low sentiment, low purchase intent, unreliable persona responses, low realism) get flagged with specific, explainable risk alerts.

#### Verification
Run against a test simulation with deliberately seeded bad feedback (mostly negative sentiment, low purchase likelihood); confirm the expected risk flags trigger. Run against clearly good feedback; confirm no false-positive flags.

#### Completion Criteria
Risk rules are threshold-configurable, explainable (each flag names which rule and why), and correctly discriminate between a clearly-risky and clearly-healthy test case.

---

## Phase 10 — Feedback-Driven Optimization Loop

### Step 25 — Heuristic Optimization Engine

#### When
After Steps 23–24 (needs sentiment and risk signals to optimize against).

#### Objective
Implement FR#8 (PRD §9) per Decision #3: heuristic/threshold weighting, not RL/Bayesian/genetic search.

**Status: ✅ Completed and fully verified (2026-08-17).**

**Implementation notes / decisions made (implemented directly, per user's fast-track instruction):**
- **Real gap found and closed, beyond this step's own file list**: `propose_next_attributes()` would have had nothing downstream able to consume its output — Step 16's `generate_variants()` had no hook at all for "narrow toward a prior result," it always sampled from a fixed per-product anchor with a fixed radius. Extended `app/ml/gan/inference.py`'s `generate_variants()` with an optional `attribute_hints` parameter (`anchor_seed`, `perturbation_radius`, `hue_shift_center_degrees`, each independently falling back to the Step 16 default if absent) and threaded it through `gan_service.generate_variants_for_simulation()`. Without this, "latent-space nudging" would have been a proposal nobody could act on, not an actual mechanism.
- Engagement proxy is reaction-text length normalized to a 200-character cap, per the plan's own suggested stand-in ("feedback length/specificity") absent an explicit engagement field.
- Risk penalty is a flat per-rule-triggered deduction (`0.3` per distinct risk rule from Step 24), not weighted by severity — kept simple since there's no labeled data to justify a more elaborate scheme yet.
- **Verified end-to-end, not just the scoring function in isolation**: built one simulation with a deliberately best variant (0.9 purchase likelihood, positive sentiment, no risk flags) and a deliberately worst one (0.1 likelihood, negative sentiment, one risk flag) — confirmed the best variant scored higher (0.673 vs -0.468) and `propose_next_attributes()` correctly picked the *best* variant's exact `anchor_seed`/hue, not the worst's. Then closed the full loop: fed that exact proposal into the newly-extended `generate_variants()` and confirmed the resulting 4 variants' hues clustered tightly at 195°-217.5° (a ±15° band around the proposed 210° center) instead of the undirected 0°-360° sweep Step 16 uses without hints — proving the nudge mechanism is real and consumed correctly, not just proposed and ignored.

#### What to Develop
A scoring/weighting function that combines sentiment, purchase-likelihood, engagement, and risk signals into a single per-variant score, and a "nudge" step that biases the next GAN generation round toward the attribute directions of the best-scoring variant(s).

#### Files to Create
- `backend/app/services/optimization_service.py`

#### Files to Modify
None beyond the new file.

#### Implementation Details
`optimization_service.score_variants(simulation_id) -> dict[variant_id, float]` computes a weighted sum (configurable weights, documented defaults) of: mean sentiment score, mean purchase likelihood, engagement proxy (e.g., feedback length/specificity or explicit engagement field if the LLM prompt is extended to request one), minus a risk penalty derived from Step 24's flags. `optimization_service.propose_next_attributes(simulation_id) -> AttributeRanges` looks at the top-scoring variant(s)' `attributes` JSON and narrows the next round's `generate_variants()` attribute ranges (Step 16) toward that neighborhood — this is the "latent-space nudging + scenario weighting" mechanism named in the Abstract, implemented as a concrete, explainable function rather than an opaque model.

#### Dependencies
Step 23, Step 24, Step 16 (attribute schema it nudges).

#### Expected Result
Given a simulation's current-round feedback, the engine produces both a ranked score per variant and a concrete attribute proposal for the next generation round.

#### Verification
Unit test with synthetic feedback where one variant is clearly better (higher sentiment/purchase-intent, no risk flags); confirm it scores highest and that `propose_next_attributes()` narrows toward its attribute values.

#### Completion Criteria
Scoring is deterministic and explainable from its inputs; next-round attribute proposal is derived directly from the top-scoring variant(s), not random.

---

### Step 26 — Iteration Loop Orchestration & Stopping Criteria

#### When
Immediately after Step 25.

#### Objective
Implement the Fig 6.4 "More Iterations?" loop with the concrete stopping rule from Decision #8 (Open Decision #6).

**Status: ✅ Completed and fully verified (2026-08-17).**

**Real off-by-one bug found and fixed before it ever ran, by tracing the plan's own required test case by hand**: a naive "check `iteration_count >= max_iterations` before incrementing" implementation, checked against the plan's own scenario 3 (`max_iterations=1` must stop after exactly one round), would have let a *second* round run first — because at the moment the check runs after round 0 finishes, `iteration_count` is still `0`, and `0 >= 1` is false. Fixed by comparing `completed_rounds = iteration_count + 1` against `max_iterations` instead, and updating `iteration_count` to that completed count in every return path (not just the "continue" path) — documented at length in the function's own docstring since this exact class of bug is easy to reintroduce.

**Implementation notes / decisions made (implemented directly, per user's fast-track instruction):**
- `PLATEAU_THRESHOLD = 0.02` — a documented constant, not tuned against any labeled data (none exists).
- Per-iteration scoring reuses Step 25's `score_variants()` rather than duplicating the scoring formula — variants are grouped by iteration via their `Feedback` rows' `iteration_number` (uniform per variant, since a variant only ever gets feedback from the one round it was generated in).
- **Verified all 3 scenarios the plan explicitly requires, against real DB state, not simulated in memory**: (1) steadily improving scores with `max_iterations=3` → `[True, True, False]`, running exactly 3 rounds; (2) a clear plateau at round 2 with `max_iterations=5` (deliberately set higher than the plateau point, so the *plateau* — not the max — is what's being tested) → `[True, True, False]`, stopping 2 rounds earlier than the max would have allowed; (3) `max_iterations=1` with a strongly improving trend → stops after exactly one round regardless — this is the exact case that caught the off-by-one bug above.

#### What to Develop
Loop-control logic that decides, after each round, whether to generate another round of variants or stop and move to final recommendation.

#### Files to Create
None — extends `optimization_service.py`.

#### Files to Modify
- `backend/app/services/optimization_service.py` — add `should_continue(simulation) -> bool`.
- `backend/app/models/simulation.py` — confirm `iteration_count`/`max_iterations` fields (already added Step 5) are sufficient; no schema change needed.

#### Implementation Details
`should_continue()` returns `False` (stop) if `simulation.iteration_count >= simulation.max_iterations` (default 3, per Decision #8) **or** if the best PMF-relevant score (from Step 25's scoring, or the eventual PMF score once Phase 12 exists) improved by less than a configurable plateau threshold versus the previous round. Otherwise returns `True` and increments `iteration_count`. This function is called by the orchestrator (Step 28), not invoked directly by any API caller — it's pure decision logic, kept testable in isolation from the orchestration plumbing around it.

#### Dependencies
Step 25.

#### Expected Result
A simulation stops after at most `max_iterations` rounds, or earlier if scores plateau — never loops indefinitely, and never stops after a single round if it's still meaningfully improving.

#### Verification
Unit test three scenarios: (1) scores keep improving each round → loop continues until `max_iterations` hit; (2) scores plateau on round 2 → loop stops early; (3) `max_iterations=1` → loop stops after exactly one round regardless of score trend.

#### Completion Criteria
Both stopping conditions work independently and together; no code path allows unbounded iteration.

---

## Phase 11 — Scenario Configuration & Simulation Orchestration

### Step 27 — Scenario Configuration API

#### When
After Phase 4 (needs a Product to configure a scenario for). Can be built in parallel with Phases 5–10; only needs to exist before Step 28.

#### Objective
Implement FR#3 (PRD §9): capture pricing strategy, target demographic, and promotional messaging as structured simulation input.

**Status: ✅ Completed and fully verified (2026-08-17).**

**Implementation notes / decisions made (implemented directly, per user's fast-track instruction):**
- `TargetDemographic`'s fields (`age_min`, `age_max`, `gender`, `income_segment`, `region`, `lifestyle`) deliberately mirror the `Persona` model's own column names exactly, not a generic `age_range` tuple — the plan's own text says "same shape as Persona attributes, enabling later matching/filtering," so matching field-for-field (not just conceptually) is what actually makes that possible.
- Added `SimulationResponse` alongside the plan's explicitly-named `SimulationCreateRequest` — Step 28's endpoint will need a response schema regardless, and colocating it here avoids revisiting this file immediately.
- The request schema's `pricing_strategy: list[PricingTier]` is a validation-time shape; the `Simulation` model's actual `pricing_strategy` column is a JSONB dict (`{"tiers": [...]}`, matching this session's own established test-data convention) — Step 28's endpoint is where these two shapes get bridged. A normal, expected difference between an API request shape and a storage shape, not an inconsistency.
- Verified all cases the plan requires plus two more: valid payload parses with correctly-typed nested `PricingTier` objects; missing `product_id` rejected with a precise `('product_id',)` error location; a pricing tier missing `price` rejected with an exact `('pricing_strategy', 0, 'price')` location (not just "something in pricing_strategy is wrong"); empty `pricing_strategy` list rejected (`min_length=1`); out-of-range `variant_count` rejected; and omitted optional fields correctly default (`variant_count=4`, `max_iterations=None` meaning "use the model's default of 3", `persona_ids=None` meaning "Step 28 picks a representative sample").

#### What to Develop
Request/response schemas and validation for the scenario-configuration fields already present on the `Simulation` model (Step 5).

#### Files to Create
- `backend/app/schemas/simulation.py`

#### Files to Modify
None beyond the new schema file (the actual `POST /simulations` endpoint that consumes it is built in Step 28, kept as one step since creating a simulation *is* configuring its scenario — the SRS's Stage 3 and the Activity Diagram's step 3 are the same action here, sidestepping PRD §13's noted stage-ordering ambiguity by treating scenario configuration as part of simulation creation, matching the Activity Diagram's earlier placement).

#### Implementation Details
`SimulationCreateRequest`: `product_id`, `pricing_strategy` (structured: e.g. list of `{tier_name, price}` for FR's "multiple pricing tiers" per PRD §18), `target_demographic` (`age_range`, `gender`, `income_segment`, `region`, `lifestyle` — same shape as `Persona` attributes, enabling later matching/filtering of which seeded personas are most relevant), `promotional_messaging` (free text), optional `persona_ids` (if omitted, default to a representative sample from the library), optional `variant_count` (default e.g. 4), optional `max_iterations` (default 3, overriding the model default from Step 5 if provided).

#### Dependencies
Step 5 (Simulation model fields), Step 11 (Product must exist).

#### Expected Result
A validated schema exists that fully captures a launch scenario, ready to be accepted by Step 28's creation endpoint.

#### Verification
Schema-level unit tests: valid payloads parse correctly; missing required fields (`product_id`) are rejected; malformed nested structures (e.g., a pricing tier missing `price`) are rejected with a clear validation error.

#### Completion Criteria
Schema captures every scenario field named in PRD §18/§9 FR#3; validation errors are specific and field-level, not generic.

---

### Step 28 — Simulation Orchestration Endpoint (End-to-End Pipeline Wiring)

#### When
After every service built in Phases 6–10 and 27 exists. This is the integration point of the entire backend.

#### Objective
Wire Generate → Simulate → Evaluate (Sentiment/Risk) → Optimize → (repeat) → Recommend into one orchestrated flow behind a single API surface, satisfying FR#4's "Run Simulation" use case (Fig 6.5) and the full Activity Diagram (Fig 6.4).

**Status: ✅ Completed and fully verified end-to-end (2026-08-17).** The single biggest integration step in the whole plan — full account below.

**Resolved a genuine circular dependency in the plan itself before writing any code**: this step's own flow calls `recommendation_service.build_recommendation()` (Step 29) as its step 5 to ever reach "completed" — but Step 29 is listed as coming *after* Step 28, and this document's own Section 5 dependency diagram has them in that same order. Step 29's own "When" text already half-acknowledges this ("called from within the orchestrator's final step... described as its own step since it satisfies a distinct FR"). Resolved by building `recommendation_service.py`'s core logic (`build_recommendation()`) together with this step, out of necessity — Step 29 itself, done separately afterward, adds only its other listed deliverable (the `GET` retrieval endpoint) on top of what's built here. Both steps' write-ups cross-reference this.

**Real, significant bug found and fixed by the end-to-end test itself, not by inspection**: the first full run produced 6 variants and 30 feedback rows in iteration 1 where exactly 3 and 15 were expected (matching iteration 0). Root cause: `ProductVariant` has no `iteration` column of its own, and `persona_service.simulate_persona_reactions()` queried "all variants for this simulation" rather than "this round's variants" — so every subsequent round silently re-simulated every earlier round's variants too, tagging them with the new iteration_number. Fixed by adding an optional `variant_ids` parameter to `simulate_persona_reactions()`, with the orchestrator now capturing `gan_service.generate_variants_for_simulation()`'s actual return value and passing those exact IDs through. Re-verified clean after the fix: iteration 0 → 3 variants/15 feedback rows, iteration 1 → 3 variants/15 feedback rows, both correct.
- `sentiment_service.classify_feedback()` and `risk_service.detect_risks()` were checked for the same class of bug and found safe: sentiment classification only touches rows still missing a label (self-limiting), and risk detection recomputing already-correct flags for old variants is redundant work, not incorrect output (flags don't change once a variant's feedback is fixed). Left as-is; a legitimate future optimization, not a correctness fix.

**Other implementation notes:**
- The orchestrator owns its own DB session (`SessionLocal()`, not the request-scoped `get_db()` dependency) since it runs via FastAPI `BackgroundTasks` outside the normal request lifecycle.
- **Verified the complete required scenario for real**, not simulated: created a real simulation via the live API (`max_iterations=2`, `variant_count=3`), polled `/status` through real state transitions (`generating` → ... → `completed`), and confirmed in the database: `iteration_count == 2` (respects the cap), exactly 3 variants + 15 feedback rows *per* iteration (6/30 total, not the buggy pre-fix numbers), every variant has a non-null `fid_score`, every feedback row has a non-null `sentiment_label`, and exactly one `Recommendation` row referencing only the *final* iteration's 3 variants (not all 6).
- **Also verified the failure path directly**, beyond what the plan's own verification asked for: (1) calling `run()` with a simulation ID that doesn't exist at all doesn't crash unhandled; (2) injecting a real mid-pipeline exception (a broken `sentiment_service.classify_feedback`) into an otherwise-real simulation run confirmed it lands in `FAILED` status, not stuck in `evaluating` or any other intermediate state — directly proving "failures are captured, not silent," not just assuming the `try/except` wrapper works.

#### What to Develop
- `POST /api/v1/simulations` — creates the `Simulation` row (from Step 27's schema) and kicks off orchestration.
- `simulation_orchestrator.py` — the actual pipeline runner.
- `GET /api/v1/simulations/{id}/status` — poll current status.

#### Files to Create
- `backend/app/services/simulation_orchestrator.py`
- `backend/app/api/v1/simulations.py`

#### Files to Modify
- `backend/app/api/v1/router.py` — include the simulations router.

#### Implementation Details
`simulation_orchestrator.run(simulation_id)`:
1. Set `status="generating"`; call `gan_service.generate_variants_for_simulation()` (Step 16), then `evaluation.py`'s FID scoring (Step 18).
2. Set `status="simulating"`; call `persona_service.simulate_persona_reactions()` (Step 21) then `check_consistency()` (Step 22).
3. Set `status="evaluating"`; call `sentiment_service.classify_feedback()` (Step 23) then `risk_service.detect_risks()` (Step 24).
4. Set `status="optimizing"`; call `optimization_service.score_variants()` and `should_continue()` (Steps 25–26). If continuing: increment `iteration_count`, call `propose_next_attributes()`, and go back to step 1 with the narrowed attribute ranges. If not continuing: proceed.
5. Call `recommendation_service.build_recommendation()` (Phase 12, Step 29).
6. Set `status="completed"`, `completed_at=now()`.

Any unhandled exception in any stage sets `status="failed"` and records the error (does not leave a simulation silently stuck in an intermediate status). Runs as a FastAPI `BackgroundTasks` job (per Decision #1: no Celery/Redis in the MVP) so `POST /simulations` returns immediately with a `202`-style response and a pollable `id`, while the actual multi-minute pipeline (LLM calls, GAN inference) runs in-process in the background. This is the one place in the codebase where every prior phase's service is called together — treat changes here as high-risk and covered thoroughly by Step 39's end-to-end test.

#### Dependencies
Steps 16, 18, 21, 22, 23, 24, 25, 26, 27. Practically: all of Phases 6–10 and Step 27.

#### Expected Result
`POST /api/v1/simulations` with a valid scenario payload runs the entire pipeline to completion (or documented failure) without further manual intervention, respecting the iteration/stopping rule from Step 26.

#### Verification
Create a simulation via the API for a test product with `max_iterations=2`; poll `/status` until `completed`; confirm `iteration_count <= 2`, variants/feedback/recommendation rows exist for every iteration, and no simulation is left stuck in a non-terminal status.

#### Completion Criteria
Full pipeline runs end-to-end via one API call; status transitions are always correct and terminal; failures are captured, not silent; iteration loop respects Step 26's stopping rule.

---

## Phase 12 — Final Recommendation Engine

### Step 29 — Ranking/PMF Scoring & Recommendation API

#### When
After Step 28 (called from within the orchestrator's final step) — described as its own step since it satisfies a distinct functional requirement (FR#10) with its own dedicated logic and API surface.

#### Objective
Implement FR#10 (PRD §9): "Optimized variants, analytics → Ranking/scoring algorithms → Recommended product variant," using the aggregate-persona-metric approach resolved in Decision #9 for "product-market fit."

**Status: ✅ Completed and fully verified (2026-08-17), split across two work sessions as described below.**

**`recommendation_service.py` and `schemas/recommendation.py` (the core scoring/ranking logic) were built during Step 28**, not here — Step 28's orchestrator calls `build_recommendation()` as its own final step and cannot reach "completed" without it, so it was built together with that step out of necessity (both steps' write-ups cross-reference this). What that already includes, verified via Step 28's real end-to-end test: PMF score normalized to a 0-100 scale, a full `ranking` JSON array (not just the winner), `recommended_variant_id` matching the actual top-ranked entry, a templated `summary_text`, and — a detail this step's own text specifically calls for — scoring is correctly scoped to the *final* iteration's variants only (added an `iteration_number` filter to Step 25's `score_variants()` to make this possible; confirmed via Step 28's test that a 2-iteration simulation's recommendation covered only the last round's 3 variants, not all 6 generated across both rounds).

**What this step itself adds:** the `GET /simulations/{id}/recommendation` retrieval endpoint in `backend/app/api/v1/simulations.py`, wired to `RecommendationResponse`. **Verified with its own dedicated end-to-end pass**, not just reusing Step 28's test: (1) calling the endpoint *before* the simulation finishes correctly returns `404` with a clear "may still be running, or may have failed" message, not a confusing empty/500 response; (2) after the simulation reached `completed`, the endpoint returned `200` with `recommended_variant_id` matching the top (first) entry in its own `ranking` array exactly, cross-checked directly against the `recommendations` table (not just trusting the API's own response); (3) ownership scoping confirmed with two separate real accounts — a second user requesting the first user's simulation's recommendation gets `404` ("Simulation not found," not leaking that it exists), matching the same non-leaking pattern established in Step 11; (4) no-auth request correctly returns `401`.

#### What to Develop
- `recommendation_service.build_recommendation(simulation_id) -> Recommendation`.
- `GET /api/v1/simulations/{id}/recommendation`.

#### Files to Create
- `backend/app/services/recommendation_service.py`
- `backend/app/schemas/recommendation.py`

#### Files to Modify
- `backend/app/api/v1/simulations.py` — add the recommendation-retrieval route.

#### Implementation Details
`build_recommendation()` takes the final iteration's variant scores (Step 25's `score_variants()`, already risk-adjusted), computes a normalized `pmf_score` per variant (0–100 scale, explicitly documented as "aggregate of persona sentiment/engagement/purchase-intent," per Decision #9 — not a market-dynamics output), builds a full `ranking` JSON array (all variants, ordered, with their component scores visible — not just the winner, so the dashboard can show a comparison), picks the top-ranked variant as `recommended_variant_id`, and generates a short `summary_text` (a templated explanation referencing the top variant's strongest signals, e.g. "Variant C scored highest on purchase intent among price-sensitive personas and carried no risk flags.").

#### Dependencies
Step 25 (scores), Step 28 (called at pipeline completion).

#### Expected Result
Every completed simulation has exactly one `Recommendation` row, with a full ranking and a human-readable summary, retrievable via API.

#### Verification
Complete a test simulation end-to-end (via Step 28's flow); confirm a `Recommendation` row exists, `recommended_variant_id` matches the actual top-scoring variant from `ranking`, and `GET /simulations/{id}/recommendation` returns it correctly.

#### Completion Criteria
Recommendation is generated automatically at the end of every completed simulation; ranking is consistent with the underlying scores; retrieval API works.

---

## Phase 13 — Dashboard & Analytics API

### Step 30 — Analytics Aggregation Endpoints

#### When
After Phase 12 (needs completed simulations with recommendations to aggregate over).

#### Objective
Implement FR#9 (PRD §9)'s backend half: "Simulation outputs, analytics → Aggregation, visualization → Interactive dashboard/reports," and the specific dashboard content named in PRD §25 (sentiment charts, scenario comparisons, PMF score, launch-risk indicators, variant ranking).

**Status: ✅ Completed and fully verified (2026-08-17).**

**Design decision not fully spelled out by this step's own text**: the plan ties PMF/ranking explicitly to `Recommendation.ranking`, which only exists once a simulation reaches `completed` (Step 28's orchestrator builds it as its second-to-last action). Rather than returning sentiment/risk/engagement computed over a different, possibly-inconsistent set of variants for a still-running simulation, this endpoint requires the same precondition Step 29's recommendation endpoint already established (`404` with a "may still be running, or may have failed" message until a `Recommendation` row exists), and scopes every section of the payload — sentiment breakdown, engagement, risk flags — to exactly the variant set recorded in that ranking. This keeps the whole response internally consistent (one variant set, every section agrees) rather than mixing in superseded earlier-round variants.

**Real pre-existing gap found and fixed while building this step, not by inspection alone**: `Feedback.engagement_score` is a column that is never actually written anywhere in the pipeline (Steps 21/23/24 all leave it `null` permanently) — the real engagement calculation only ever existed as a private on-the-fly proxy (`_engagement_proxy`, reaction-text length normalized to [0,1]) inside `optimization_service.score_variants()`. Querying the column directly for this endpoint would have silently returned `null` for every variant. Fixed by making that function public (`engagement_proxy`, one-line rename, no logic change) and reusing it here rather than duplicating the same logic in a second place — a small, deliberate touch to `optimization_service.py` outside this step's own listed files, justified by "reuse existing utilities" over shipping broken analytics or copy-pasted logic.

**Verified end-to-end against the real, live API**, cross-checked against the database directly (not just trusted from the API response): created a simulation (`max_iterations=1`, `variant_count=2`), confirmed `GET /analytics` returns `404` with the "may still be running" message before completion, polled to `completed`, then confirmed `200` with a fully-shaped payload — 2 variants ranked 1/2, `is_recommended` correctly true only for rank 1, sentiment counts (5 neutral/0/0/0 per variant, matching the disclosed no-LLM-key gap producing classifiable-but-uninformative `[LLM_ERROR]` text), non-null `avg_engagement_score` (confirming the reuse fix works — this would have been `null` without it), correct risk flags (`low_purchase_likelihood`, `low_realism_fid`, matching the underlying thresholds), and matching `fid_score`. Every one of these values was independently re-queried straight from Postgres and matched exactly. Also verified ownership scoping (a second real account requesting the first account's simulation gets `404` "Simulation not found," not a leak) and no-auth (`401`).

#### What to Develop
Read-only aggregation endpoints the frontend dashboard (Phase 14) will consume directly.

#### Files to Create
- `backend/app/schemas/dashboard.py`
- `backend/app/api/v1/dashboard.py`

#### Files to Modify
- `backend/app/api/v1/router.py` — include the dashboard router.

#### Implementation Details
`GET /api/v1/simulations/{id}/analytics` returns one composed payload: per-variant sentiment distribution (counts of positive/negative/neutral from `Feedback`), per-variant PMF score and rank (from `Recommendation.ranking`), risk indicators (aggregated `risk_flags` per variant), engagement scores, and the scenario configuration echoed back for context. All scoped to the requesting user's own simulations (or any simulation, for an admin). No new computation happens here — this endpoint only reads and reshapes data already produced by Phases 6–12; keeping it read-only avoids duplicating business logic that belongs in the services built earlier.

#### Dependencies
Step 29, Step 24 (risk flags), Step 23 (sentiment).

#### Expected Result
A single API call returns everything the dashboard UI needs to render for one simulation, without the frontend needing to call five different endpoints and stitch results together itself.

#### Verification
Call the endpoint for a completed test simulation; confirm the response contains correctly-shaped sentiment counts, PMF ranking, and risk indicators matching what's in the underlying tables.

#### Completion Criteria
Endpoint returns a complete, correctly-scoped analytics payload for any completed simulation; ownership/admin access rules are enforced.

---

### Step 31 — Report Export (PDF/CSV)

#### When
Immediately after Step 30.

#### Objective
Implement the explicit "Download Reports (PDF/CSV export)" use case named in Fig 6.5.

**Status: ✅ Completed and fully verified (2026-08-17).** `reportlab==5.0.0` added to `requirements.txt` (per the plan's own preference over `weasyprint`, to avoid a system Pango/Cairo dependency).

Reuses the same "only a completed simulation has a `Recommendation` to report on" precondition as Step 30 (`404` beforehand, same message style). CSV flattens Feedback joined against Persona name and ProductVariant metadata (one row per persona×variant, plus a final ranking section); PDF is a templated 1-2 page report (scenario summary, recommendation text, PMF ranking table, deduplicated risk flags per variant) built with `reportlab.platypus`.

**Verified against the real, live API**: confirmed `404` before completion; after completion, downloaded both `?format=csv` and `?format=pdf` with correct `Content-Type`/`Content-Disposition` headers. CSV content was read directly and matched the underlying data exactly (same simulation/recommendation IDs, correct PMF ranking, correct risk flag for the triggered rule). PDF was verified structurally (valid `%PDF` header and `%%EOF` trailer, non-trivial size) — built from the same shared data-loading helper as the CSV path, so its content is generated from data already cross-checked via the CSV; no PDF viewer was available to visually confirm layout. Also verified `422` on an invalid `format` value (FastAPI's own `Literal["csv","pdf"]` validation, no extra code needed) and ownership scoping (`404` for a second real account, `401` with no auth).

#### What to Develop
Report generation service producing a PDF and a CSV export of a simulation's results.

#### Files to Create
- `backend/app/services/report_service.py`

#### Files to Modify
- `backend/app/api/v1/dashboard.py` — add `GET /api/v1/simulations/{id}/report?format=pdf|csv`.
- `backend/requirements.txt` — add a PDF-generation library (e.g. `reportlab` or `weasyprint`; prefer `reportlab` — no external binary/system dependency, simpler deployment).

#### Implementation Details
CSV export: flatten `Feedback` + `Recommendation` rows for the simulation into a single tabular file (one row per persona×variant, plus a final ranking section) using the standard library's `csv` module — no need for `pandas` here given the modest size and the "don't add a dependency the stack already solves" guidance. PDF export: a simple, templated one-to-two-page report (scenario summary, top recommendation, PMF ranking table, key risk flags) via `reportlab`. Both are generated on-demand (not pre-generated/cached), since simulation results don't change after `completed` status.

#### Dependencies
Step 30 (source data), Step 29 (recommendation content).

#### Expected Result
A user can download a correctly-formatted CSV or PDF for any of their completed simulations.

#### Verification
Call the endpoint with both `format=csv` and `format=pdf` for a completed test simulation; confirm both files download, open correctly, and contain the expected data (spot-check a few values against the DB).

#### Completion Criteria
Both export formats work, contain accurate data, and are scoped to the requesting user's own simulations (or admin access).

---

## Phase 14 — Frontend Application

### Step 32 — API Client & Auth State

#### When
Can begin as soon as Phase 3 (auth API) exists — does not need to wait for the full backend.

#### Objective
Give every later frontend page a working, authenticated way to call the backend.

**Status: ✅ Completed (2026-08-17).** Token stored in `localStorage` under `dryrunai_token`; `apiFetch` attaches it automatically and clears it + redirects to `/login` on any `401`. `AuthContext` re-validates the stored token against `GET /auth/me` on mount (not just trusting a locally-cached user object), so a stale/invalid token is caught immediately rather than after the first failed request. `isAdmin` is derived live from `/auth/me`'s `role` field rather than decoding the JWT client-side — always reflects current DB state, avoids an extra dependency. See Step 37's note: this was verified directly (promoted a user's role mid-session, confirmed the *existing* token immediately reflected admin access with no re-login), which happens to also confirm this part of Step 32 works correctly.

#### What to Develop
- A fully wired API client (extends Step 3's stub) with JWT attachment and 401-handling.
- React auth context (login/logout/current-user state, token persistence).

#### Files to Create
- `frontend/src/api/auth.ts`
- `frontend/src/state/AuthContext.tsx`

#### Files to Modify
- `frontend/src/api/client.ts` — attach `Authorization: Bearer <token>` from context/local storage on every request; on a 401 response, clear the token and redirect to `/login`.
- `frontend/src/App.tsx` — wrap the app in `AuthProvider`.

#### Implementation Details
Store the JWT in memory + `localStorage` (acceptable for this project's threat model — no more sensitive than any other JWT-in-browser SPA, consistent with the SRS's own JWT-based auth requirement). `AuthContext` exposes `user`, `login(email, password)`, `logout()`, `isAuthenticated`. A `<ProtectedRoute>` wrapper component redirects unauthenticated users to `/login`.

#### Dependencies
Step 9 (login endpoint), Step 3 (frontend scaffold).

#### Expected Result
The frontend can log in, persist the session across a page reload, attach auth headers automatically, and redirect to login on session expiry.

#### Verification
Manually log in via the (still-placeholder) login page once Step 33 exists; confirm the token persists across a refresh and that an expired/invalid token correctly redirects to `/login`.

#### Completion Criteria
Auth state and API client are fully wired; every subsequent authenticated page can rely on them without reimplementing token handling.

---

### Step 33 — Auth Pages (Register + Login)

#### When
Immediately after Step 32.

#### Objective
Replace the Step 3 placeholder routes with real registration/login forms.

**Status: ✅ Completed (2026-08-17).** Matches Step 8/9's real contract exactly (register needs `org_name`, not just email/password -- confirmed against `schemas/auth.py` before writing the form, avoiding a guessed field). No auto-login after registration, per the plan's own design.

#### What to Develop
Functional `/register` and `/login` pages.

#### Files to Create
None — replace placeholders.

#### Files to Modify
- `frontend/src/pages/RegisterPage.tsx`
- `frontend/src/pages/LoginPage.tsx`
- `frontend/src/router.tsx` — confirm routing to these.

#### Implementation Details
Simple controlled forms (org name/email/password for register; email/password for login) calling `api/auth.ts`, with inline field-level validation errors surfaced from the backend's 4xx responses (per Step 8/9's validation). Successful login calls `AuthContext.login()` and redirects to `/dashboard`. Successful registration redirects to `/login` with a success message (no auto-login, keeping the flow explicit and matching Step 8's design).

#### Dependencies
Step 32, Step 8, Step 9.

#### Expected Result
A new user can register and then log in through the actual UI, ending up authenticated in the app.

#### Verification
Manual browser test: register a new account, confirm redirect to login, log in, confirm redirect to dashboard and that the auth token is present.

#### Completion Criteria
Both forms work end-to-end against the real backend; validation errors from the API are shown to the user, not swallowed.

---

### Step 34 — Product Upload UI

#### When
After Step 33 (needs auth) and Step 11 (needs the products API).

#### Objective
Implement the "Upload Product" use case (Fig 6.5).

**Status: ✅ Completed (2026-08-17).**

**Real gap found while building this step, not by inspection**: there was no way to actually view an uploaded image over HTTP at all -- `original_image_path`/`preprocessed_image_path` were only ever filesystem-relative paths, and no static file mount or image-serving route existed anywhere in the backend. A blanket public `StaticFiles` mount was deliberately rejected: every other resource in this app (products, simulations, recommendations, analytics, reports) is ownership-scoped with a 404-not-403 pattern, and a public mount at a guessable path would let anyone enumerate UUIDs and view other users' photos without authentication -- a real regression from the rest of the app's security posture. Added `GET /api/v1/products/{id}/image?kind=original|preprocessed` instead, routed through the existing `get_product()` ownership check (`backend/app/api/v1/products.py`). Since a plain `<img src>` can't attach an `Authorization` header, the frontend fetches the bytes via `apiFetchBlob` and renders them through a reusable `AuthenticatedImage` component (`frontend/src/components/AuthenticatedImage.tsx`) using an object URL.

**Verified against the real, live API**: uploaded a real product through the exact multipart shape the frontend sends, confirmed `GET /products` and `GET /products/{id}/image` both return correctly (200, correct `Content-Type`, and the fetched bytes decode back to a valid 512x512 JPEG via Pillow).

#### What to Develop
A form for name/description/category/branding details plus an image file input, submitting as multipart to `POST /api/v1/products`.

#### Files to Create
None — replace the Step 3 placeholder.

#### Files to Modify
- `frontend/src/pages/ProductUploadPage.tsx`
- `frontend/src/api/products.ts` (new)

#### Implementation Details
Client-side validation mirrors the backend's constraints from Step 11 (image type/size) so users get immediate feedback rather than a round-trip error. On success, show the uploaded product with a preview and a clear next action ("Configure a launch scenario for this product") linking into Step 35.

#### Dependencies
Step 33, Step 11.

#### Expected Result
A logged-in user can upload a product with an image through the UI and see it listed afterward.

#### Verification
Manual browser test: upload a product, confirm it appears in a product list view, confirm the stored image renders correctly.

#### Completion Criteria
Upload works end-to-end through the UI; validation errors are shown clearly; uploaded product is immediately usable for the next step (scenario configuration).

---

### Step 35 — Scenario Configuration & Simulation Trigger UI

#### When
After Step 34 and Step 28 (needs the simulation-orchestration API).

#### Objective
Implement "Configure Scenarios" and "Run Simulation" (Fig 6.5).

**Status: ✅ Completed (2026-08-17).**

**Real gap found while building this step**: there was no endpoint to list a user's own past simulations -- only create-by-POST and fetch-by-known-UUID existed. Without it, a user would have no way back to a simulation's results except by keeping the URL from the moment it was created. Added `GET /api/v1/simulations` (same "list mine, or everyone's for an admin" pattern already used by `list_products`), needed by both this step's progress page and Step 36's dashboard landing view.

Scenario form matches Step 27's schema field-for-field (confirmed against `schemas/simulation.py` before writing it). Progress page polls every 4s and renders each pipeline stage from `SIMULATION_STAGE_LABELS`, with a distinct terminal state for both `completed` (link to results) and `failed` (explicit error, not an infinite spinner).

**Verified against the real, live API**: created a simulation through the exact JSON shape the frontend sends, confirmed the response matches the `Simulation` TypeScript interface field-for-field, and confirmed `GET /simulations` (list) returns it correctly.

#### What to Develop
A form capturing pricing tiers, target demographic, promotional messaging, and simulation options (variant count, max iterations), submitting to `POST /api/v1/simulations`, followed by a progress view polling `GET /simulations/{id}/status`.

#### Files to Create
- `frontend/src/pages/ScenarioConfigPage.tsx` (replaces placeholder)
- `frontend/src/pages/SimulationRunPage.tsx` (replaces placeholder)
- `frontend/src/api/simulations.ts`

#### Files to Modify
- `frontend/src/router.tsx` — route `/simulations/new` → config page, `/simulations/:id` → run/progress page.

#### Implementation Details
Scenario form matches Step 27's schema shape exactly (pricing tiers as a dynamic list, demographic fields, messaging text area). On submit, navigate to the progress page, which polls status every few seconds and shows the current pipeline stage (generating/simulating/evaluating/optimizing) using the `status` field from Step 28, with a clear terminal state (link to the dashboard on `completed`, an error display on `failed`).

#### Dependencies
Step 34, Step 27, Step 28.

#### Expected Result
A user can configure a scenario and trigger a full simulation run, watching it progress to completion (or a clear failure state) without needing to check the API directly.

#### Verification
Manual browser test: configure and trigger a simulation for a real uploaded test product, watch it progress through all stages to `completed`, confirm the UI correctly reflects each backend status transition.

#### Completion Criteria
Scenario submission and progress polling work correctly against the real orchestrator; failure states are shown, not left as an infinite spinner.

---

### Step 36 — Dashboard & Analytics UI

#### When
After Step 35 and Step 30 (needs the analytics API).

#### Objective
Implement "View Analytics" (Fig 6.5) with the specific content PRD §25 names: sentiment charts, scenario comparisons, PMF score, launch-risk indicators, design-variant ranking.

**Status: ✅ Completed (2026-08-17).**

**Routing decision beyond this step's literal file list**: a dashboard inherently needs to know *which* simulation to show, but the Step 3 scaffold only ever defined a bare `/dashboard` route. Added `dashboard/:id` in `router.tsx`; `DashboardPage.tsx` (the one file the plan names) handles both cases itself via `useParams` -- no `id` renders a "your simulations" list view (using Step 35's new list endpoint), an `id` renders the full analytics view. This also gives the nav bar's "Dashboard" link somewhere sensible to go without requiring a UUID in hand.

**Real gap found while building this step**: the plan's own text calls for "an expandable per-persona feedback list... so the qualitative 'why' behind the scores is visible" -- but Step 30's `/analytics` payload only ever carried aggregate sentiment counts, never individual persona reactions. Extended `VariantAnalytics` with a `feedback: PersonaFeedbackEntry[]` field (persona name, qualitative text, purchase likelihood, sentiment label) rather than adding a second endpoint and a round-trip per variant -- more consistent with Step 30's own stated goal ("one composed payload... frontend doesn't need to stitch together several endpoints"). Also added `GET /simulations/{id}/variants/{variant_id}/image` (same ownership-scoped pattern as Step 34's product image endpoint) so `VariantCard` can render each generated image.

Components: `VariantCard` (image, `PMFScoreGauge`, `SentimentChart`, `RiskAlertList`, and an expandable `PersonaFeedbackList`), laid out as a comparison grid -- satisfying "scenario comparisons" the same way the plan's own Implementation Details describes it, not a separate component. The recommended variant gets a highlighted border + badge, not just top-of-list placement. `recharts@3.10.1` added to `package.json` for the pie chart (sentiment) and radial gauge (PMF score).

**Verified against the real, live API, not just TypeScript types**: fetched a real `/analytics` response and confirmed every field --  including the new `feedback` array -- matches the frontend's interfaces key-for-key; fetched a real variant image through the new endpoint and confirmed it decodes to a valid image. **Honest limitation**: no browser/screenshot tool is available in this environment, so rendering itself (layout, chart appearance, whether the gauge/pie actually look right) was not visually confirmed -- only that the code compiles, builds for production cleanly, and every piece of data it depends on is real and correctly shaped. Worth an eyeball pass (`npm run dev`) before presenting.

#### What to Develop
The dashboard page rendering `GET /simulations/{id}/analytics`'s payload.

#### Files to Create
- `frontend/src/pages/DashboardPage.tsx` (replaces placeholder)
- `frontend/src/api/dashboard.ts`
- `frontend/src/components/VariantCard.tsx`
- `frontend/src/components/SentimentChart.tsx`
- `frontend/src/components/PMFScoreGauge.tsx`
- `frontend/src/components/RiskAlertList.tsx`
- `frontend/src/components/PersonaFeedbackList.tsx`

#### Files to Modify
- `frontend/package.json` — add a charting library (`recharts`) for sentiment/comparison charts.

#### Implementation Details
Layout: a variant comparison grid (`VariantCard` per generated variant, showing its image, PMF score, rank, FID score), a sentiment breakdown chart, a risk-alert panel (from Step 24's flags), and an expandable per-persona feedback list (from Step 21's qualitative text) so the qualitative "why" behind the scores is visible, not just aggregate numbers. The recommended variant (Step 29) is visually highlighted, not just listed at the top of a table.

#### Dependencies
Step 35, Step 30.

#### Expected Result
A completed simulation's full results are viewable and comparable in one screen, matching every dashboard content item named in the PRD.

#### Verification
Manual browser test against a completed test simulation with multiple variants/personas; visually confirm sentiment chart, PMF scores, risk alerts, and per-persona feedback all render correctly and match the underlying API response.

#### Completion Criteria
All PRD §25-named dashboard content is present and correctly rendered; recommended variant is visually distinguished.

---

### Step 37 — Report Download & Admin Panel UI

#### When
After Step 36 and Step 31 (report API) / Step 10 (admin dependency).

#### Objective
Implement "Download Reports" (Fig 6.5) and the Admin actor's UI (Fig 6.3: manage users, monitor simulations).

**Status: ✅ Completed (2026-08-17).** Report download buttons added to `DashboardPage.tsx` (blob fetched with auth header via `apiFetchBlob`, then the standard anchor-download pattern for the actual browser save -- a plain `<a href>` can't carry the `Authorization` header the report endpoint requires). `backend/app/api/v1/admin.py` added exactly as specified: `GET /admin/users` and `GET /admin/simulations`, both behind `get_current_admin_user` (Step 10), read-only (no destructive admin action is named in the certified scope). `AdminPage.tsx` is a straightforward two-table view; `/admin` is guarded client-side by `AdminRoute`, but the real security boundary is the backend's `403`, verified independently of the frontend guard.

**Verified against the real, live API**: downloaded both CSV and PDF reports through the exact endpoint/query-param shape the frontend uses (both `200`). Promoted a real test user to `admin` directly in the database, confirmed their *already-issued* token immediately gained access to both admin endpoints with no re-login required (confirms `get_current_user` re-fetches the live DB role on every request rather than trusting a stale JWT claim) and that both returned correctly-shaped data. Confirmed a second, non-admin real account gets a real `403` ("Admin privileges required") from the backend directly -- the actual access-control boundary, not just the frontend route guard.

#### What to Develop
- A download button/menu on the dashboard page for PDF/CSV export.
- A separate admin-only page listing all users and all simulations across the system.

#### Files to Create
- `frontend/src/pages/AdminPage.tsx` (replaces placeholder)

#### Files to Modify
- `frontend/src/pages/DashboardPage.tsx` — add report download actions calling `GET /simulations/{id}/report`.
- `frontend/src/router.tsx` — guard `/admin` behind `isAdmin` (from `AuthContext`, populated from the JWT's `role` claim).
- `backend/app/api/v1/admin.py` (new, backend-side) — `GET /api/v1/admin/users`, `GET /api/v1/admin/simulations`, both behind `get_current_admin_user` (Step 10).
- `backend/app/api/v1/router.py` — include the admin router.

#### Implementation Details
Download triggers a `fetch`/`axios` request with the appropriate `Accept`/response-type handling for binary PDF vs. text CSV, then a browser-native file save (standard anchor-download pattern, no special backend support beyond returning correct `Content-Type`/`Content-Disposition` headers). Admin page is a straightforward read-only table view — no admin write actions are required by the certified scope (PRD §12 only says Admin "manages users and monitors simulations," and no destructive admin action is specified, so none is built beyond viewing).

#### Dependencies
Step 36, Step 31, Step 10.

#### Expected Result
Users can download a PDF or CSV report from the dashboard; an admin account can view all users and all simulations system-wide; a non-admin cannot reach `/admin` or its API routes.

#### Verification
Manual browser test: download both formats and open them; log in as an admin test account and confirm the admin page lists all users/simulations; confirm a non-admin account is blocked from `/admin` (redirected) and from the underlying API (403).

#### Completion Criteria
Report downloads work in both formats; admin visibility works and is correctly access-controlled.

---

## Phase 15 — Testing & Hardening

### Step 38 — Backend Unit & Integration Test Suite

#### When
Runs continuously alongside every backend phase in practice (each step above already specifies its own verification), but this step is where the suite is consolidated, filled in for anything under-tested, and run as a whole for the first time.

#### Objective
Ensure every service and endpoint built in Phases 2–13 has an automated test, not just the manual verification described per-step.

**Status: ✅ Completed (2026-08-17). 54 tests, 93% coverage of this project's own code** (excludes the vendored NVIDIA StyleGAN2-ADA reference implementation and the deliberately-deferred `finetune.py` — both explicitly `omit`-ted via a new `backend/.coveragerc`, so the reported number reflects code this project actually authored and is meant to test at this stage, not padded or deflated by either).

**A real correctness problem caught and fixed before writing a single test on top of it**: the obvious "wrap each test in one transaction, roll it back after" isolation pattern is actually broken for this codebase, because services call `db.commit()` internally (`register_user`, `create_product`, etc.) — a plain session bound to that transaction would let those commits escape the rollback and leak real rows into the test database permanently. Fixed using SQLAlchemy's documented pattern for exactly this situation: bind the test session to a `SAVEPOINT`, and restart a fresh savepoint every time the app's own code ends one via `commit()`, so the *outer* transaction's rollback is always what actually undoes everything. Verified this wasn't just theoretical by re-running the same test file twice in a row before writing anything else — a broken version would have failed the second run on duplicate-email conflicts.

**A second, structural constraint discovered while building the E2E test**: `simulation_orchestrator.run()` deliberately opens its own `SessionLocal()` (a separate DB connection) since it runs as a background task outside the request-scoped session lifecycle (Step 28's own architecture decision) — and a savepoint on *one* connection is genuinely invisible to a second, independent connection (real transaction isolation, not a testing bug). The rollback-isolated fixtures can't reach this case at all. Added a second fixture, `committed_client`, used only where needed: real commits against `dryrunai_test` (never the real `dryrunai` database), with every table truncated at teardown, and both the request-scoped session and the orchestrator's own `SessionLocal` pointed at the same test engine — mirroring exactly how the two connections relate in production.

**Mocking strategy** (per this step's own guidance, "verifying pipeline mechanics... not image quality"): only the two genuinely expensive/external boundaries are mocked — a tiny random-weight `nn.Module` stands in for the real 364MB GAN checkpoint (`fake_gan_generator`), and a deterministic-but-varied fake stands in for the real Anthropic API (`fake_llm_provider`, Step 20's own `Protocol` design made this a clean swap with zero production-code changes). Sentiment classification (a real, already-cached HuggingFace model) and FID computation (real `torchmetrics`) are left genuinely real in every test — both fast once warmed, and exactly the kind of real integration worth actually proving.

**Also fixed**: product/variant image uploads write real files to disk via `storage_service`, which isn't transactional — without isolating this too, every upload-touching test would leave real files under `backend/storage/` with nothing to clean them up. Added an `autouse` fixture redirecting `STORAGE_ROOT` to pytest's own `tmp_path` for every test.

**One deviation from the plan's exact file list**: added `tests/test_admin.py` (not originally named) and one oversized-upload test in `test_products.py` — both close specific gaps in Step 40's own verification text ("calling an admin endpoint as a regular user should 403"; "oversized... upload should 4xx") that weren't otherwise covered by an automated test, turning one-off manual checks into permanent regression tests instead.

#### What to Develop
`pytest` test modules covering models, services, and API routes, using a test database (or transactional rollback per test) and mocked external calls (LLM provider, GAN inference kept fast/deterministic via a tiny test checkpoint or a mock generator).

#### Files to Create
- `backend/tests/conftest.py` (test DB fixture, test client fixture, auth-header fixture, mocked LLM provider fixture)
- `backend/tests/test_auth.py`
- `backend/tests/test_products.py`
- `backend/tests/test_ingestion.py`
- `backend/tests/test_gan_inference.py`
- `backend/tests/test_persona_service.py`
- `backend/tests/test_sentiment_service.py`
- `backend/tests/test_risk_service.py`
- `backend/tests/test_optimization_service.py`
- `backend/tests/test_recommendation_service.py`
- `backend/tests/test_dashboard.py`

#### Files to Modify
- `backend/requirements.txt` — add `pytest-cov` for coverage reporting.

#### Implementation Details
`conftest.py`'s test DB fixture points at a separate test database (or uses SQLite only if fully compatible with the JSON column usage — otherwise a dedicated `dryrunai_test` Postgres DB is safer given JSON/enum usage, matching production behavior more closely). LLM provider tests use a fake `LLMProvider` implementation (Step 20's `Protocol` makes this trivial) returning fixed responses, so the suite doesn't depend on network access or API cost. GAN tests use a tiny random-weight generator for speed, not the real pretrained checkpoint, verifying the pipeline mechanics (correct output count/shape/persistence) rather than image quality.

#### Dependencies
All of Phases 2–13 (this step tests them).

#### Expected Result
`pytest` runs the full suite and passes; coverage report shows meaningful coverage (not necessarily 100%, but every service/endpoint has at least its documented happy-path and one failure-path test).

#### Verification
```
cd backend
pytest --cov=app
```
All tests pass; coverage report reviewed for obvious gaps.

#### Completion Criteria
Suite covers every phase's core service/endpoint; runs deterministically without real network/API calls; passes cleanly.

---

### Step 39 — End-to-End Pipeline Test Pass

#### When
After Step 38.

#### Objective
Verify the full user journey (Fig 6.4 Activity Diagram) works as one continuous flow, not just as individually-passing unit tests.

**Status: ✅ Completed and passing (2026-08-17).** `test_e2e_pipeline.py` drives the real FastAPI app through every stage named in the Activity Diagram in one continuous flow: register → login → upload product → seed personas (the real operational precondition `scripts/seed_personas.py` satisfies in production — without it, `select_representative_personas()` returns nothing and the whole simulation would fail with no feedback to recommend from, a real dependency this test makes explicit rather than silently working around) → configure scenario → run simulation with `max_iterations=2` (exercising a real full iteration of the optimization loop, not just a single round) → poll to `completed` → view analytics → fetch the recommendation → download both report formats. A useful confirmation along the way: `TestClient` executes `BackgroundTasks` inline before returning the POST response, so by the time `POST /simulations` returns in the test, the entire pipeline (both rounds) has already run — the polling loop is defensive/mirrors the real frontend rather than strictly necessary here.

Every response is asserted against the actual TypeScript-facing contract, and the final state is cross-checked directly against the database (not just trusted from API responses): exactly 4 variants (2 rounds × 2/round), exactly 4 feedback rows, and the recommendation's `recommended_variant_id` matching what the analytics endpoint reported.

#### What to Develop
One integration test that drives the system exactly as a real user would: register → login → upload product → configure scenario → run simulation → poll to completion → view analytics → download report.

#### Files to Create
- `backend/tests/test_e2e_pipeline.py`

#### Files to Modify
None.

#### Implementation Details
Uses `httpx`'s test client against the real FastAPI app (with the same mocked LLM/GAN fixtures as Step 38, so it's still fast and deterministic) to call every endpoint in sequence, asserting on the response at each stage and on final DB state (variants, feedback, recommendation, all present and consistent). This is the test that would have caught any integration gap between phases that unit tests, working against phases in isolation, could miss.

#### Dependencies
Step 38 (fixtures/mocks reused), and functionally, every phase through Phase 13.

#### Expected Result
The entire documented user journey passes as a single automated test.

#### Verification
`pytest backend/tests/test_e2e_pipeline.py -v` passes.

#### Completion Criteria
Full journey test passes reliably (not flaky) and exercises every stage named in the Activity Diagram, including at least one iteration of the optimization loop.

---

### Step 40 — Security Review Pass

#### When
After Step 39, once the full system is functionally complete.

#### Objective
Verify the NFR security requirements (PRD §10, §29: SSL/TLS, JWT/OAuth, DB security) and general OWASP-top-10 hygiene are actually met, not just assumed.

**Status: ✅ Completed (2026-08-17) — a clean pass, every checklist item verified against the real code, not assumed.** No fixes were required; every item genuinely held up:
- **Passwords**: never appear in any response schema (`UserResponse` carries only `id/org_name/email/role`) or in any `logger` call — confirmed by grep, not memory.
- **JWT secret**: only ever read from `settings.JWT_SECRET_KEY` (env-sourced); grepped the whole codebase for a hardcoded value and found none.
- **Every endpoint requires auth** (not just mutating ones): enumerated all 15 non-auth routes across `products.py`/`simulations.py`/`dashboard.py`/`admin.py` directly from source and confirmed every single one carries `Depends(get_current_user)` or `Depends(get_current_admin_user)` — only `/auth/register`, `/auth/login`, and `/health` are (correctly) public.
- **Ownership scoping**: consistent 404-not-403 pattern across products, simulations, and the two image-serving endpoints added this phase — verified by both the automated suite and, for the two new endpoints, a real path-traversal check (the file path served always originates from a DB value this app itself wrote at upload/generation time, never directly from a request parameter, so there's no way to smuggle a `../` through `kind` or any other input).
- **File upload validation**: content-type/extension whitelist + 10MB size cap, verified with a real oversized-upload test (new this step).
- **SQL access**: grepped for any raw/string-interpolated query across `backend/app` *and* both standalone scripts (`scripts/ingest_dataset_pipeline.py`, `backend/scripts/seed_personas.py`) — everything goes through the ORM or parameterized `sqlalchemy.dialects.postgresql.insert()`.
- **CORS**: config-driven via `CORS_ORIGINS`, currently the real dev frontend origin, never a `*` wildcard anywhere in the code.
- **No committed secrets**: `git grep` across tracked `.py`/`.ts`/`.tsx`/`.env*` files for API-key/password/secret patterns found nothing; confirmed no `.env` file is tracked by git at all.
- **Admin escalation**: `promote_to_admin()` exists only as a service-layer function, never wired to any router — grepped to confirm no endpoint calls it. Verified with a real regular-user account hitting `/admin/users`/`/admin/simulations` and getting a real `403` (new automated test, not just the manual check performed back in Step 37).

**One thing noted but deliberately not built**: there's no rate-limiting/brute-force protection on `/auth/login`. This isn't on this step's own checklist and would be new scope (a dependency like `slowapi` plus a request-counting store), not a "fix a finding" task — flagged here as a disclosed, known gap rather than silently added or silently ignored.

#### What to Develop
No new features — a review pass with any fixes it surfaces.

#### Files to Create
None (unless fixes require new files).

#### Files to Modify
Whatever the review finds — tracked and fixed individually, not batched into unrelated changes.

#### Implementation Details
Checklist to walk through: passwords never logged or returned (Step 8); JWT secret loaded from env, never hardcoded (Step 9); every mutating endpoint requires auth (Steps 9–37); ownership checks prevent cross-user data access (Step 11 pattern, applied consistently); file upload validation prevents arbitrary file execution (Step 11); SQL access goes through the ORM everywhere (no raw string-interpolated queries anywhere in Phases 2–13); CORS is restricted to the actual frontend origin in production config (not `*`); secrets (`JWT_SECRET_KEY`, LLM API key, DB credentials) are only ever in `.env`/environment, never committed (confirmed via `git log`/`git grep` for accidental commits); admin escalation is not reachable via any public API (Step 10).

#### Dependencies
Step 39 (system must be functionally complete to review meaningfully).

#### Expected Result
A documented pass confirming each checklist item, with any findings fixed before moving to deployment.

#### Verification
Manually attempt: accessing another user's product/simulation by guessing an ID (should 403/404); calling an admin endpoint as a regular user (should 403); submitting an oversized/wrong-type file upload (should 4xx); confirm `git grep -i "sk-\|api_key\|secret"` across tracked files shows no committed secrets.

#### Completion Criteria
Every checklist item passes; any findings during the review are fixed and re-verified before Phase 16.

---

## Phase 16 — Deployment

### Step 41 — Containerization

#### When
After Phase 15 (deploy a system that's already known to work correctly).

#### Objective
Package the backend and frontend as Docker images, satisfying the Portability NFR (PRD §10: "Web-based, containerization (Docker)").

**Status: ✅ Completed and fully verified (2026-08-17) — the full stack was actually built and run via `docker compose up`, not just written and assumed correct.**

**A real bug found and fixed by actually building the image, not by inspection**: the first attempt filtered `requirements.txt`'s CUDA-pinned `torch`/`torchvision` lines out, installed everything else, then installed CPU-only `torch`/`torchvision` from PyTorch's dedicated CPU index as a separate step. That silently didn't work — `transformers`/`torchmetrics`/`torch-fidelity` all transitively depend on `torch` too, so the *first* `pip install` step already resolved and installed a torch build from the default index (bundling ~1.5GB of unused NVIDIA CUDA runtime libraries) to satisfy those, and the later explicit CPU-index install saw "already satisfied" and did nothing. Confirmed by reading the actual install log, not assumed. Fixed by reordering: install `torch`/`torchvision` from the CPU index *first*, then the rest of `requirements.txt` — re-built and re-read the log to confirm zero `nvidia-*`/`cuda-*`/`triton` packages appear this time. Final image: 2.48GB (down from a CUDA-bundled build that would have been meaningfully larger — image size directly affects Step 42's pull time/cost).

**A second real issue caught before it mattered**: no `.dockerignore` existed for either service, so `COPY . .` would pull the *host's* `node_modules` (Windows-installed) and the backend's `.venv`/364MB GAN checkpoint/test suite into the build context -- 124MB and 52 seconds just for the frontend's context transfer on the first build. Beyond wasted time, copying a Windows-built `node_modules` into a Linux container risks shadowing the correctly-installed Linux-native modules `npm ci` just produced. Added `.dockerignore` for both services (`node_modules`/`dist`/`.git` for frontend; `.venv`/`__pycache__`/`storage`/`tests`/`.git` for backend).

**Design decisions**: `backend/entrypoint.sh` runs `alembic upgrade head` before `uvicorn` on every container start, so migrations are never a manual, forgettable step. The GAN checkpoint is a bind mount (`./backend/storage:/app/storage`), not baked into the image or a named volume — it already exists on the host, and a named volume would start empty and need a separate copy-in step. The frontend is a genuine multi-stage build (`node` build stage -> `nginx:alpine` serving only the static output); `nginx.conf` proxies `/api/*` to the `backend` service so the browser only ever talks to one origin (no CORS needed for the real deployed path), which is also why `frontend/.env.production` sets `VITE_API_BASE_URL` to an explicit empty string rather than a real host -- `import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'`'s `??` only falls back on an *unset* value, so this has to be a defined empty string, not just omitted.

**Verified end-to-end against the real, running containers**, not just a successful build: `docker compose up` brought up `db` (healthy) -> `backend` (migrations ran, `uvicorn` started cleanly) -> `frontend` (nginx workers started) with zero manual steps beyond the already-populated root `.env`. Confirmed nginx's `/api` proxy actually reaches the backend (a real `401` from `/api/v1/auth/me` through port 80, not port 8000 directly). Ran the full smoke test through the containerized, nginx-proxied path exactly as the plan's own verification text specifies: register -> login -> upload a real product -> run a real simulation (the *real* GAN checkpoint this time, on CPU, inside the container -- not the test suite's mocks) -> completed -> dashboard analytics returned correctly -> variant image served correctly -> PDF report downloaded correctly. Also confirmed the bind mount works in both directions: the variant image the *container* generated during this run is directly readable from the host filesystem afterward. Test data cleaned up; personas (20) and the GAN checkpoint preserved.

#### What to Develop
Production Dockerfiles for both services, and a full `docker-compose.yml` (extending Step 4's dev-only Postgres compose) covering backend + frontend + db together.

#### Files to Create
- `backend/Dockerfile`
- `frontend/Dockerfile`
- `frontend/nginx.conf` (serve the built static frontend)

#### Files to Modify
- `docker-compose.yml` (root) — add `backend` and `frontend` services alongside the existing `db` service.

#### Implementation Details
`backend/Dockerfile`: multi-stage or single-stage `python:3.11-slim` base, installs `requirements.txt`, copies `app/`, runs `alembic upgrade head` then `uvicorn` at container start (via an entrypoint script so migrations always run before serving). `frontend/Dockerfile`: multi-stage — `node` build stage running `npm run build`, then an `nginx:alpine` stage serving the static output, with `nginx.conf` proxying `/api` to the backend service. Model checkpoints (Step 15's GAN weights) are mounted as a volume, not baked into the image (they're large binaries that shouldn't bloat the image or need rebuilding on every code change).

#### Dependencies
Step 40 (system verified before packaging it).

#### Expected Result
`docker compose up` (from a clean checkout, with a populated `.env`) brings up the full working system — db, backend, frontend — with no manual steps beyond providing environment variables.

#### Verification
From a clean clone (or a clean directory copy) with only `.env` populated, run `docker compose up --build`; confirm the frontend is reachable in a browser and a full manual smoke test (register → upload → simulate → dashboard) works against the containerized stack.

#### Completion Criteria
Full stack builds and runs via Docker Compose alone; no undocumented manual setup step remains.

---

### Step 42 — Cloud Deployment

#### When
Immediately after Step 41.

#### Objective
Satisfy the Scalability/Availability NFRs' documented approach (PRD §10: cloud infra, auto-scaling, backups) at a scale appropriate for an academic capstone demo — not a full multi-region production rollout.

#### What to Develop
Deployment of the Step 41 images to a single cloud target, plus a managed Postgres instance.

#### Files to Create
- `docs/deployment.md` (concrete, copy-pasteable deployment runbook — hosting provider, exact steps, one-time setup)

#### Files to Modify
None in application code — this step is operational/configuration, executed against whichever provider is chosen (AWS/Azure/GCP, all named as acceptable in PRD §26).

#### Implementation Details
Pragmatic choice for an academic project's scale and budget: one managed container-hosting service (e.g., a single App Service/Container App/Cloud Run instance per backend and frontend) plus one managed Postgres instance, rather than building out Kubernetes/load-balanced multi-instance infrastructure that Phase-3-scope NFR wording gestures at but nothing in the certified functional requirements actually forces for a working demo. Environment variables/secrets are configured through the provider's secret-management UI, never committed (consistent with Step 40). Document the exact provider, region, and resource names chosen at deployment time in `docs/deployment.md` so the setup is reproducible.

#### Dependencies
Step 41.

#### Expected Result
The system is reachable over the public internet at a stable URL, backed by a managed database, with no secrets in source control.

#### Verification
Access the deployed frontend URL from a browser outside the local network; complete a full manual smoke test against the live deployment (register → upload → simulate → dashboard → report download).

#### Completion Criteria
System is publicly reachable, functionally correct in production, and its setup is documented well enough for someone else on the team to reproduce or redeploy it.

---

### Step 43 — Production Verification

#### When
Immediately after Step 42 — the final step of Phase 16.

#### Objective
Confirm the deployed system actually satisfies the NFRs it claims to, not just that it's reachable.

#### What to Develop
No new code — a verification pass with a short written record of results.

#### Files to Create
- `docs/production_verification.md` (dated checklist results)

#### Files to Modify
None.

#### Implementation Details
Verify: HTTPS is enforced (SSL/TLS NFR); a fresh browser session with no cached token cannot reach any protected page/data; the full E2E journey (same as Step 39, run manually against production) succeeds; a simulation with real GAN + real LLM calls (not the test mocks) completes successfully end-to-end at least once, since Steps 38–39 only ever exercised mocked versions of those two external-dependency-heavy pieces; database backups are enabled on the managed Postgres instance (even a basic automated daily backup, per the Reliability NFR).

#### Dependencies
Step 42.

#### Expected Result
A signed-off record that the live, deployed system meets its documented non-functional requirements, and that the real (non-mocked) GAN/LLM path has been exercised at least once outside of tests.

#### Verification
Manual execution of every item above against the live deployment; results recorded in `docs/production_verification.md`.

#### Completion Criteria
Every verification item passes against the real deployment; at least one real (non-mocked) end-to-end simulation run is confirmed successful in production.

---

## Phase 17 — Phase-3 Enhancements (Optional, Post-MVP)

**Everything in this phase is explicitly outside certified scope (Decision #1) and is not required to consider the project done (see §10). Undertake only after the Phase 16 milestone (§6, M6) is reached, and only if time/scope allows.**

### Step 44 — Vector Knowledge Base (FAISS) for RAG-Grounded Persona Prompts

#### When
After Phase 16, optional. Independent of Steps 45–47.

#### Objective
Improve persona-reaction quality by grounding LLM prompts in real review text (`ref_reviews`, ingested in Step 13), per the Lit_Review.pdf Phase-3 architecture's RAG-style context injection.

#### What to Develop
Embedding + retrieval of relevant review snippets, injected into Step 20's prompt construction.

#### Files to Create
- `backend/app/ml/retrieval/__init__.py`
- `backend/app/ml/retrieval/vector_store.py` (FAISS index build/query)
- `backend/app/ml/retrieval/embeddings.py` (Sentence-Transformer embedding wrapper)

#### Files to Modify
- `backend/app/ml/llm/prompt_templates.py` — accept and include retrieved context.
- `backend/requirements.txt` — add `faiss-cpu`, `sentence-transformers`.

#### Implementation Details
Build a FAISS index over `ref_reviews.review_text` embeddings (Sentence-Transformers) for the relevant product category at simulation time (or precomputed and refreshed after each ingestion run); at prompt-construction time, retrieve the top-k most relevant real reviews for the persona's segment and inject them as grounding context, clearly labeled as reference material in the prompt (not presented to the LLM as the persona's own memory).

#### Dependencies
Step 20, Step 13 (needs real `ref_reviews` data to be worth doing — low value against fixture-scale data).

#### Expected Result
Persona reactions reference realistic, grounded product feedback patterns rather than being purely template-driven.

#### Verification
Compare persona outputs with and without retrieval context on the same product/persona pair; confirm retrieval-augmented outputs reference concrete, plausible product attributes consistent with the retrieved reviews.

#### Completion Criteria
Retrieval measurably changes/improves prompt content; index build is repeatable after each ingestion run.

---

### Step 45 — Async Task Queue (Celery + Redis)

#### When
After Phase 16, optional.

#### Objective
Replace Step 28's in-process `BackgroundTasks` with a proper async task queue, matching the Lit_Review.pdf Phase-3 architecture, for better reliability/scalability under real concurrent load.

#### What to Develop
Celery worker configuration, Redis broker, migration of `simulation_orchestrator.run()` from a `BackgroundTasks` call to a Celery task.

#### Files to Create
- `backend/app/core/celery_app.py`
- `backend/app/tasks/simulation_tasks.py`

#### Files to Modify
- `backend/app/api/v1/simulations.py` — dispatch to Celery instead of `BackgroundTasks`.
- `docker-compose.yml` — add `redis` and `worker` services.
- `backend/requirements.txt` — add `celery`, `redis`.

#### Implementation Details
`simulation_orchestrator.run()`'s logic is unchanged — only its invocation moves from an in-process background task to a Celery task dispatched via `task.delay(simulation_id)`, run by a separate worker process/container. This is a deliberately low-risk change since Step 28 was already structured as a single, self-contained orchestration function.

#### Dependencies
Step 28, Step 41 (containerized deployment target for the extra services).

#### Expected Result
Simulations run on a separate worker process, surviving a backend API restart mid-simulation (which `BackgroundTasks` does not).

#### Verification
Trigger a simulation, restart the backend API container mid-run, confirm the simulation still completes via the worker; confirm Redis/worker health via `docker compose ps`.

#### Completion Criteria
Task queue correctly replaces in-process background execution with no behavior change to the orchestration logic itself.

---

### Step 46 — Dynamic LLM-Generated Personas

#### When
After Phase 16, optional. Builds on Step 19's library.

#### Objective
Extend Decision #4's curated library with dynamically LLM-authored personas per simulation, closing the "not yet resolved" half of Open Decision #3.

#### What to Develop
An LLM-driven persona-authoring function, used as an optional addition to (not replacement for) the seeded library.

#### Files to Create
- `backend/app/services/dynamic_persona_service.py`

#### Files to Modify
- `backend/app/models/persona.py` — none needed (`source="dynamic"` already reserved in Step 5).
- `backend/app/api/v1/simulations.py` — add an opt-in flag (`generate_dynamic_personas: bool`) to simulation creation.

#### Implementation Details
Given a simulation's target-demographic fields, prompt the LLM provider (Step 20) to author 2–3 additional personas beyond the seeded set matching that specific demographic more precisely than any fixed template can, following the same structured-output contract Step 21 already parses. Persist these as `Persona` rows with `source="dynamic"`, scoped to that simulation only (not added to the shared library). Explicitly retains and prefers the seeded library as the default (`generate_dynamic_personas` defaults to `false`) — this is additive, not a replacement, keeping the more-reproducible curated path as the system's primary behavior.

#### Dependencies
Step 19, Step 20, Step 21, Step 28.

#### Expected Result
When opted in, a simulation includes a small number of freshly-authored personas tailored to its specific scenario, alongside the standard curated set.

#### Verification
Run a simulation with the flag enabled; confirm new `Persona` rows with `source="dynamic"` are created and produce feedback like any other persona in the pipeline.

#### Completion Criteria
Dynamic persona generation works as an additive, opt-in path; does not change default behavior for simulations that don't request it.

---

### Step 47 — Experiment Tracking (MLflow)

#### When
After Phase 16, optional. Most useful once Step 17 (fine-tuning) is being run against real data.

#### Objective
Track GAN fine-tuning runs and key model metrics over time, per the Lit_Review.pdf Phase-3 architecture's Model Ops layer.

#### What to Develop
MLflow logging integrated into the Step 17 fine-tuning script.

#### Files to Create
None — extends existing file.

#### Files to Modify
- `backend/app/ml/gan/finetune.py` — log parameters, loss curves, and the resulting checkpoint as an MLflow run/artifact.
- `docker-compose.yml` — add an `mlflow` tracking-server service.
- `backend/requirements.txt` — add `mlflow`.

#### Implementation Details
Wrap the existing fine-tuning loop with `mlflow.start_run()`, logging hyperparameters (epochs, learning rate, dataset size/version from `source_dataset_version`), per-epoch loss, and the final checkpoint file as an artifact, so successive fine-tuning attempts (as real pipeline data grows) are comparable rather than each being an untracked, overwritten checkpoint.

#### Dependencies
Step 17.

#### Expected Result
Every fine-tuning run is recorded in MLflow with its parameters, metrics, and resulting checkpoint, browsable via the MLflow UI.

#### Verification
Run `finetune.py` against fixture data; confirm a new run appears in the MLflow UI with logged parameters/metrics and a downloadable checkpoint artifact.

#### Completion Criteria
Fine-tuning runs are tracked and comparable; no fine-tuning run happens outside of MLflow tracking going forward.

---

# 5. Dependency Order

```
Step 1 (git init)
   ↓
Step 2 (backend scaffold) ──┐
Step 3 (frontend scaffold) ─┤
   ↓                        │
Step 4 (local dev env, Postgres)
   ↓
Step 5 (domain models) → Step 6 (migrations) → Step 7 (reference tables)
   ↓
Step 8 (register) → Step 9 (JWT login) → Step 10 (RBAC)
   ↓
Step 11 (product upload) → Step 12 (preprocessing)
   ↓                                              ↓
Step 13 (ingest pipeline) → Step 14 (persona    Step 15 (GAN checkpoint)
   seed extraction)                                 ↓
   ↓                                              Step 16 (variant generation)
   │                                                 ↓         ↓
   │                                       Step 17 (fine-tune)  Step 18 (FID)
   ↓                                                 (parallel, optional-blocking)
Step 19 (persona library) → Step 20 (LLM provider) → Step 21 (persona reactions) → Step 22 (consistency)
   ↓                                                                  ↓
   │                                                          Step 23 (sentiment)
   │                                                                  ↓
   │                                                          Step 24 (risk detection)
   │                                                                  ↓
   │                                                          Step 25 (optimization scoring) → Step 26 (iteration/stopping)
   ↓                                                                  ↓
Step 27 (scenario schema) ───────────────────────────────────────────┤
   ↓                                                                  ↓
                    Step 28 (ORCHESTRATION — needs 16,18,21,22,23,24,25,26,27)
                                       ↓
                              Step 29 (recommendation)
                                       ↓
                    Step 30 (analytics API) → Step 31 (report export)
                                       ↓
        Step 32 (API client/auth state) → Step 33 (auth pages)
                                       ↓
        Step 34 (product upload UI) → Step 35 (scenario/run UI) → Step 36 (dashboard UI) → Step 37 (reports/admin UI)
                                       ↓
                    Step 38 (unit/integration tests) → Step 39 (E2E test) → Step 40 (security review)
                                       ↓
                    Step 41 (containerize) → Step 42 (cloud deploy) → Step 43 (prod verification)
                                       ↓
        ═══════════════════════ MVP COMPLETE (Phases 1–16) ═══════════════════════
                                       ↓  (optional, any order among these four)
        Step 44 (vector KB) │ Step 45 (Celery/Redis) │ Step 46 (dynamic personas) │ Step 47 (MLflow)
```

**Parallelizable work** (once their listed prerequisites are met): Steps 15–18 (GAN) and Steps 19–26 (persona/sentiment/risk/optimization) can be built by different team members simultaneously once Step 12 exists — they only converge at Step 28. Step 3 (frontend scaffold) and Step 32 onward can similarly run on a separate track from backend Phases 5–13, converging as each backend endpoint becomes available. Steps 44–47 have no dependencies on each other and can be split across team members if pursued.

---

# 6. Milestone Plan

- **M1 — Accounts & Uploads work** (after Step 12): A user can register, log in, and upload a product with an image. Nothing else works yet, but the foundation is real and demoable.
- **M2 — A product produces GAN variants** (after Step 18): Given an uploaded product, the system generates N distinct, scored design variants. No personas/simulation yet.
- **M3 — Variants get simulated** (after Step 24): Personas react to variants with sentiment and risk scoring attached. The "AI core" of the system is functionally proven, even without the full orchestration/loop wired together yet.
- **M4 — Full loop produces a recommendation** (after Step 29): One API call runs the entire Generate→Simulate→Evaluate→Optimize→Recommend loop, respecting iteration/stopping rules, and produces a ranked recommendation. This is the point at which every certified functional requirement's backend logic exists.
- **M5 — Certified MVP complete** (after Step 37): Full React frontend covers every use case in Fig 6.5 — the system is usable end-to-end by a real (non-technical) user, satisfying all 10 functional requirements and all 8 NFRs at MVP scope.
- **M6 — Deployed and verified** (after Step 43): The system is live, reachable, containerized, and its NFRs have been checked against the real deployment, not just locally. This is the certified-scope project's true "done" milestone.
- **M7 — Enhanced (optional)** (after any of Steps 44–47): Selected Phase-3 capabilities added, each independently — no requirement to complete all four.

---

# 7. Final Integration Sequence

1. **Database + backend core**: Steps 5–10 establish schema and auth before any feature logic is built on top of it.
2. **Storage + first feature vertical**: Step 11–12 prove the upload→storage→preprocessing path end-to-end for one feature, establishing the pattern (ownership scoping, validated input, service-layer separation) every later feature reuses.
3. **External data integration**: Steps 13–14 bring the dataset pipeline's output into the system's own database as reference data, ahead of anything that consumes it.
4. **AI/ML components, built independently, integrated once**: Steps 15–26 build GAN generation, persona/LLM simulation, sentiment, risk, and optimization as independently testable services against fixtures/mocks — genuinely wired together for the first time in Step 28's orchestrator, not incrementally bolted on.
5. **APIs + frontend, grown together**: Step 27 onward, each backend capability (scenario config, orchestration, recommendation, analytics, reports) gets its API before the corresponding frontend page (Steps 32–37) is built against it — frontend work never runs ahead of a real, tested backend contract.
6. **Authentication threads through everything above it**: every API from Step 11 onward is built behind the Step 9/10 auth dependencies from the start, not retrofitted later.
7. **Error handling**: each service step (Steps 11, 21, 28 especially) specifies its own failure behavior (validation rejection, per-pair failure isolation, terminal `failed` status) as part of building the feature, not as a separate later pass — Step 40's security review checks this was actually done consistently, it doesn't do it for the first time.
8. **Testing**: Step 38 consolidates and fills gaps in the per-step verification already performed throughout; Step 39 proves integration; Step 40 proves security posture — in that order, because integration bugs are cheaper to find before a security-focused review than after.
9. **File/storage systems**: local filesystem storage (Step 11) is used consistently through Steps 15–18's checkpoint/variant storage — no second storage mechanism is introduced.
10. **Deployment**: only begins (Step 41) once Steps 38–40 have passed — the system being packaged and shipped is the same one already verified to work and to be reasonably secure.
11. **Optional Phase-3 integration**: Steps 44–47 each integrate into exactly one existing seam (prompt construction, task dispatch, persona creation, fine-tuning script) without altering the MVP's core contracts — each is a genuinely optional addition, not a prerequisite the MVP path depends on.

---

# 8. Testing and Validation Plan

Testing is embedded per-step (every step in Section 4 specifies its own Verification), not deferred to the end. This section defines what happens at each *stage* of the project and the cross-cutting passes that only make sense once multiple phases exist.

- **Unit testing**: every service function (Steps 8–29) gets a direct unit test as part of Step 38, using mocked LLM/GAN dependencies (Step 20's `Protocol` interface and a lightweight test generator make this practical without real API cost or GPU time in CI).
- **Integration testing**: API-route-level tests (request → DB state) for every endpoint, also part of Step 38; the full-journey test in Step 39 is the top-level integration test.
- **API testing**: every endpoint's happy path and at least one failure path (missing auth, invalid input, ownership violation) is tested — pattern established at Step 11, enforced consistently through Step 38.
- **UI testing**: manual browser verification is specified at every Phase 14 step (Steps 33–37); a UI change is not "done" per this plan's own rules until it has actually been exercised in a browser, not just built.
- **Error/edge cases**: LLM call failures (Step 21), GAN generation failures, oversized/invalid uploads (Step 11), expired/invalid tokens (Step 9), cross-user access attempts (Step 40) are all explicitly tested, not assumed away.
- **Security testing**: Step 40's dedicated pass, covering auth, ownership, input validation, secret handling, and CORS — after the system is functionally complete so the review is against real, final endpoints.
- **Performance testing**: no dedicated load-testing step is included in the MVP scope — the certified NFR performance targets ("low latency," "GPU acceleration") are addressed architecturally (async orchestration in Step 28, GPU-backed inference in Step 15) rather than benchmarked against a formal SLA, which is consistent with an academic capstone's actual grading criteria; if genuine load testing becomes necessary, it belongs alongside Step 45 (async queue) since that's the point synchronous bottlenecks would first become visible under concurrency.
- **End-to-end testing**: Step 39 (automated, mocked externals) and Step 43 (manual, real externals, in production) — deliberately two separate passes, since a mocked E2E test proves orchestration correctness while a real-external E2E pass proves the actual GAN/LLM integration works, which mocks cannot prove.

---

# 9. Deployment Plan

1. **Environment configuration**: `.env` files (backend, frontend, root compose) hold all environment-specific values; `.env.example` in each location documents every variable (introduced incrementally at Steps 2, 3, 9, 20, established in full by Step 41).
2. **Environment variables/secrets**: `DATABASE_URL`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES`, `STORAGE_ROOT`, `LLM_PROVIDER` + its API key, `VITE_API_BASE_URL`, plus (Phase 17 only, if pursued) `REDIS_URL`, `CELERY_BROKER_URL`. Never committed; production values live in the cloud provider's secret manager (Step 42), never in `docker-compose.yml` directly.
3. **Database setup**: local dev via Step 4's Compose Postgres; production via a managed Postgres instance (Step 42); schema applied via `alembic upgrade head` on every deploy (baked into the backend container's entrypoint, Step 41) — no manual schema application step.
4. **Build process**: backend — install `requirements.txt` into the container image (Step 41); frontend — `npm run build` producing static assets served by nginx (Step 41).
5. **Hosting**: single managed container-hosting target per service (backend, frontend) plus managed Postgres, on whichever of AWS/Azure/GCP is chosen at Step 42 (all three are SRS-acceptable, PRD §26).
6. **Backend deployment**: containerized FastAPI app (Step 41), deployed to the chosen host (Step 42), migrations run automatically on startup.
7. **Frontend deployment**: containerized static build behind nginx (Step 41), deployed alongside the backend (Step 42), configured with the production `VITE_API_BASE_URL` at build time.
8. **External services**: the LLM provider (Step 20) requires a real, funded API key in production — provisioned and stored in the cloud secret manager before Step 43's real-external verification pass. No other external service is required for MVP scope (Phase 17's Redis/MLflow are the only additional external services, and only if that phase is pursued).
9. **Production verification**: Step 43 — HTTPS enforced, auth boundaries hold, full manual E2E journey passes, at least one real (non-mocked) GAN+LLM simulation completes successfully, backups enabled on the managed database.

---

# 10. Final Definition of Done

The certified-scope MVP (Phases 1–16) is done when every item below is true. Phase 17 items are explicitly **not** required for this checklist.

- [ ] All 10 certified Functional Requirements (PRD §9) are implemented and demonstrable: registration/login, product upload, scenario configuration, GAN generation, persona simulation, sentiment analysis, risk detection, feedback optimization, dashboard, final recommendation.
- [ ] All 7 class-diagram entities (PRD §12/Fig 6.3) are correctly persisted and related, with the one documented elaboration (`ProductVariant`) and the one documented simplification (`Admin` as a `User.role`) both traceable back to this document's rationale.
- [ ] A user can complete the full journey — register → upload → configure → simulate → view dashboard → download report — through the real UI against the real backend, with no manual database intervention required at any step.
- [ ] The optimization loop respects its documented stopping criteria (max-iterations or score-plateau) on every run; no simulation can loop indefinitely or terminate before at least one full evaluation.
- [ ] Product-market-fit scoring is correctly implemented as the documented aggregate-persona metric (Decision #9) — no undocumented economic-model behavior is silently present or absent.
- [ ] Generated variants have both a realism score (FID) and, for a sample of persona responses, a consistency-variance signal — the evaluation gap flagged in PRD §31 is closed at MVP scope, not left open.
- [ ] The dataset-pipeline ingestion script runs successfully against currently-available data (fixtures today, real data once externally produced) and populates all five reference tables idempotently.
- [ ] Full automated test suite (Step 38) and end-to-end test (Step 39) pass; security review checklist (Step 40) is fully checked off with no open findings.
- [ ] System is deployed, publicly reachable over HTTPS, backed by a managed database with backups enabled, and has had at least one successful real (non-mocked) end-to-end simulation run verified in production (Step 43).
- [ ] No secrets are present anywhere in version control, at any commit.
- [ ] Every decision in "Decisions This Document Resolves" (top of this file) has been implemented as stated, or any deviation is itself documented with equivalent rationale.

When every box above is checked, the certified-scope DryRunAI system is complete. Phase 17 items remain available as clearly-optional, independently-addable future work — exactly as PRD.md's own Future Extensions (§36) and the Phase-3 architecture (§11) describe them.
