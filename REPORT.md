# DryRunAI — Implementation Report

**A GAN-centric generative AI framework for pre-launch product simulation and product-market-fit optimisation.**
Academic capstone, BMS College of Engineering, Dept. of ISE, AY 2025–26.

This document records what was actually built, how it works, and — importantly — where the implementation departed from the original plan and why. Several of those departures were forced by measured failures rather than preference, and they are reported here with the evidence that drove them rather than quietly folded in.

Companion documents: [`PRD.md`](PRD.md) (requirements), [`IMPLEMENTATION.md`](IMPLEMENTATION.md) (step-by-step build plan and per-step status), [`docs/deployment.md`](docs/deployment.md) (deployment runbook).

---

## 1. What the system does

A user uploads a product concept (image + description + branding). The system then:

1. **Generates design variants** of that product with a GAN.
2. **Simulates customer reactions** by prompting an LLM to role-play a library of predefined personas against each variant.
3. **Analyses that feedback** — sentiment classification, rule-based risk detection.
4. **Optimises** — scores variants, nudges generation toward better-performing regions, and repeats for a bounded number of iterations.
5. **Recommends** the best variant with a product-market-fit (PMF) score, viewable on a dashboard and exportable as PDF/CSV.

The point is to test a product concept *before* committing to manufacturing, using simulated rather than recruited customers.

---

## 2. Technology stack

| Layer | Choice | Version |
|---|---|---|
| Backend | FastAPI | 0.141.1 |
| Server | Uvicorn | 0.52.3 |
| ORM / migrations | SQLAlchemy 2.0 (typed declarative) / Alembic | 2.0.52 / 1.19.1 |
| Database | PostgreSQL (via `psycopg` v3) | 16 |
| Frontend | React + Vite + TypeScript | React 19 / Vite 8 |
| Routing / state | react-router-dom, React Context | — |
| Charts | Recharts | — |
| ML runtime | PyTorch (CUDA 12.6) | 2.13.0 |
| Generative model | FastGAN via `lightweight-gan` | 1.2.1 |
| Realism metric | `torchmetrics` FID + `pytorch-fid` | 1.9.0 / 0.3.0 |
| Sentiment | HuggingFace `transformers` | 5.15.0 |
| LLM | Ollama running `llama3.1:8b` locally | Ollama 0.34.3 |
| LLM (alternative) | Anthropic SDK | 0.122.0 |
| Auth | `python-jose` (JWT) + `passlib`/`bcrypt` | 3.5.0 / 4.0.1 |
| Reports | ReportLab | 5.0.0 |
| Containerisation | Docker Compose (Postgres + backend + nginx frontend) | — |

**Development hardware:** Windows 11, NVIDIA RTX 4050 Laptop GPU (6GB VRAM). The VRAM ceiling shaped several decisions recorded below.

---

## 3. Architecture

Built as a **modular monolith**: one FastAPI application whose internal module boundaries mirror the certified 7-layer architecture, rather than literally separate deployed services. For a 4-person academic team, deploying five microservices would add operational cost with no requirement forcing it; the boundaries keep a future split possible.

```
                          React SPA (Vite)
                                │  JWT in Authorization header
                                ▼
                    FastAPI  /api/v1  routers
       auth │ products │ simulations │ dashboard │ admin
                                │
                                ▼
                        Service layer
   product · storage · image_preprocessing · gan · persona
   sentiment · risk · optimization · recommendation · report
                    simulation_orchestrator
                                │
             ┌──────────────────┼──────────────────┐
             ▼                  ▼                  ▼
        ML modules         PostgreSQL        Local filesystem
   gan/ llm/ nlp/       app tables +        storage/products,
                        ref_* corpus        storage/fastgan
```

### Request flow for a simulation

`POST /api/v1/simulations` validates the scenario, creates the row, and returns **202 Accepted** immediately, dispatching `simulation_orchestrator.run()` to a FastAPI `BackgroundTask`. The client polls `GET /simulations/{id}/status`. The orchestrator then loops:

```
generate variants (GAN)
   → score realism (FID)
   → persona reactions (LLM, one call per persona × variant)
   → sentiment classification
   → risk detection
   → optimisation scoring
   → stop? (max iterations OR PMF plateau)  ── no ──▶ nudge latents, repeat
                                             └─ yes ─▶ build recommendation
```

A simulation with 5 personas × 3 variants × up to 3 iterations is ~45 LLM calls, landing in the low single-digit minutes.

---

## 4. Data model

Eight application tables plus five read-only reference tables. Current row counts on the development database:

| Table | Purpose | Rows |
|---|---|---|
| `users` | Accounts; `role` enum (`user`/`admin`) | 3 |
| `products` | Uploaded concepts, image paths | 3 |
| `product_variants` | GAN-generated variants, `attributes` JSONB, `fid_score` | 28 |
| `simulations` | Scenario config, status enum, iteration counters | 5 |
| `personas` | Predefined persona library | 20 |
| `simulation_personas` | Many-to-many association | 23 |
| `feedback` | One row per persona × variant: text, purchase likelihood, sentiment, risk flags | 136 |
| `recommendations` | Final ranking, PMF score, summary | 3 |
| **`ref_products`** | Reference corpus from the dataset pipeline | **109,808** |
| **`ref_images`** | | **46,272** |
| **`ref_reviews`** | | **496,592** |
| **`ref_market`** | | **36,096** |
| **`ref_product_intelligence`** | | **41,945** |

Two deliberate deviations from the certified class diagram, both documented in code:

- **`ProductVariant` is an added entity.** The diagram implies it (FR#4 says "GAN generates synthetic variations") without naming it, but `Feedback` must reference a *specific* variant rather than the parent product.
- **`Admin` is a `role` column, not a table.** It reproduces the same relationships the diagram specifies without a redundant entity.

The `ref_*` tables carry **no foreign keys** into application tables — the pipeline's `product_id` namespace is separate from `products.id`. They are a queryable corpus, not a relational extension.

Two Alembic migrations: `0001_initial_schema`, `0002_reference_tables`.

---

## 5. API surface

All under `/api/v1`, all JWT-protected except register/login.

| Method | Path | Notes |
|---|---|---|
| POST | `/auth/register` | 201; 409 on duplicate email |
| POST | `/auth/login` | Form-encoded (OAuth2 standard), returns JWT |
| GET | `/auth/me` | Current user |
| POST | `/products` | `multipart/form-data`; validates MIME, extension, 10MB cap |
| GET | `/products`, `/products/{id}` | Scoped to owner |
| GET | `/products/{id}/image` | Auth-gated image serving |
| POST | `/simulations` | **202**, dispatches background orchestration |
| GET | `/simulations` | List |
| GET | `/simulations/{id}/status` | Poll target |
| GET | `/simulations/{id}/recommendation` | Final result |
| GET | `/simulations/{id}/variants/{vid}/image` | Variant image |
| GET | `/simulations/{id}/analytics` | Dashboard aggregation |
| GET | `/simulations/{id}/report?format=pdf\|csv` | Export |
| GET | `/admin/users`, `/admin/simulations` | Admin-only (403 otherwise) |

**Ownership leaks are treated as information disclosure:** requesting another user's resource returns **404, not 403**, so the API never confirms that an unowned resource exists.

---

## 6. Components in detail

### 6.1 Authentication
bcrypt password hashing (`passlib`), JWT access tokens (`python-jose`) carrying `sub` and `role`. No refresh-token flow — a single short-lived token satisfies the stated requirement without added complexity. Two dependencies, `get_current_user` and `get_current_admin_user`, guard every protected route.

**Admin promotion is deliberately not an API route.** `auth_service.promote_to_admin()` exists as an operational helper only; self-service promotion is a security hole no requirement asked for.

### 6.2 Product upload and preprocessing
Validates content type, extension whitelist and size *before* writing anything to disk — no orphaned files from rejected uploads. Images are normalised to RGB at 256×256 (`image_preprocessing.TARGET_SIZE`), which is the resolution the whole pipeline standardises on. Storage sits behind a two-function interface (`save_upload`, `get_path`) so object storage could replace the local filesystem without touching callers.

### 6.3 GAN generation
`gan_service` → `inference.generate_variants()` produces N variants from one product by:
- deriving a deterministic **anchor latent** from the product ID (so repeat runs are reproducible),
- taking small **perturbations** around that anchor for structural/texture variation,
- applying a real **HSV hue shift** for colourway variation.

`load_generator()` dispatches on file extension: `.pt` → FastGAN, `.pkl` → StyleGAN2. Both expose `.z_dim` and return a `(3, 256, 256)` tensor in `[0,1]`, so everything downstream is architecture-agnostic.

### 6.4 Realism scoring (FID)
FID is a **set-vs-set** statistic, so all variants from one generation batch share a single score — "one image's FID" is not a meaningful quantity, and this is stated in code rather than silently assumed. Returns `None` rather than a misleading `NaN` when the sample is too small (< 2 images) for the covariance estimate to mean anything. Small-sample FID against a single product's own reference images is a rough signal, not a benchmark.

### 6.5 Persona simulation
20 seeded personas spanning lifestyle (Budget Shopper, Premium User, Athletic/Active, Trend-driven, Family-focused), income segment, region (US/EU/APAC) and age band. For each persona × variant, a prompt is built and sent to the LLM, and the structured reply becomes a `Feedback` row.

**Failures are isolated per pair:** one failed LLM call records an `[LLM_ERROR]`-marked row and the simulation continues, rather than aborting the whole run.

`check_consistency()` re-runs a sample of pairs and records how far the output drifts, as a lightweight evaluator-reliability signal.

### 6.6 Sentiment, risk, optimisation, recommendation
- **Sentiment** — a HuggingFace transformer classifies each reaction; `sentiment_label` and `sentiment_score` are populated as a separate stage from generation, per the certified layering.
- **Risk** — rule-based flags (high negative-sentiment ratio, low purchase likelihood, unreliable persona signal, poor realism).
- **Optimisation** — weighted score over mean sentiment, mean purchase likelihood, and an engagement proxy. Stops on max-iterations **or** PMF plateau, whichever comes first.
- **Recommendation** — ranks variants, normalises to a 0–100 PMF score, writes a human-readable summary.

`engagement_score` is intentionally never persisted: it is derived from reaction length and recomputed where needed, so the dashboard and the optimiser can't drift apart.

### 6.7 Frontend
Seven pages (`Login`, `Register`, `ProductUpload`, `ScenarioConfig`, `SimulationRun`, `Dashboard`, `Admin`) and six components (`PMFScoreGauge`, `SentimentChart`, `VariantCard`, `RiskAlertList`, `PersonaFeedbackList`, `AuthenticatedImage`). Auth lives in a React Context; a thin `apiFetch<T>()` wrapper centralises JSON handling, error unwrapping and the JWT header — chosen over adding `axios`, since the stack didn't need it.

`AuthenticatedImage` exists because images are auth-gated: a plain `<img src>` can't send a bearer token, so it fetches as a blob and renders an object URL.

---

## 7. The dataset pipeline

An archived, separately-built 7-stage ETL pipeline ships with the project. It was **code-complete but had never produced a single record** — `project_manifest.json` showed every count at zero.

**The key discovery on picking it up: it was never a scraper.** Class names like `NikeCollector` and `AmazonReviewCollector` imply live collection, but every one of them is a local-file parser. Nothing in the pipeline makes an HTTP request except the image downloader. Populating it therefore meant building an *acquisition layer*, not "running the pipeline".

Sources used, all public and legitimate — **no brand or retail site is scraped**:
- **UT-Zappos50K** — 50,025 catalog images (academic-use licence)
- **Amazon Reviews 2023** (McAuley Lab, via Hugging Face) — reviews and product metadata, streamed and filtered rather than downloaded whole
- **Wikipedia / Wikidata public APIs** — brand facts

Twelve new scripts under `_ingestion_tools/` handle acquisition, conversion, linking and orchestration. Final output: **109,808 products, 46,272 images, 496,592 reviews, 36,096 price records, 41,945 brand-intelligence rows** — 730,713 rows ingested into the `ref_*` tables with **zero broken references and zero orphans**.

### A note on the pipeline's own quality score

`project_manifest.json` reports `dataset_health_score: 17`, and five of six per-dataset scores are `0`. **That number is a scorer artifact, not a verdict on the data.** The scorer subtracts a *fixed penalty per row* with no normalisation and a floor of zero — it had only ever run against 4-row fixtures. 24,534 products with no matching review is −49,068 points on its own. Any real-scale dataset scores 0 under it.

What the underlying reports actually show: **0 duplicate IDs, 0 broken references, 0 schema violations** across all six datasets. The only missing-required field is `source_url` on the 24,522 Zappos products, which that dataset simply doesn't provide. Missing relationships are the honest, predicted non-overlap between two independent sources — not corruption.

---

## 8. Major changes during implementation

This section is the reason this document exists. Three significant departures from the plan were made, each forced by measurement.

### 8.1 LLM provider: Anthropic API → local Ollama

**Planned:** Anthropic's API as the persona-reasoning engine.

**Problem:** Steps 20–21 shipped with a disclosed verification gap — *no real LLM call had ever succeeded*. With no API key configured, every `Feedback` row in the database (60 of 60) carried an `[LLM_ERROR]` placeholder. FR#5, the core feature, had never actually run.

**Why not just buy a key:** a Claude Pro subscription does not include API usage; the API bills separately per token.

**Resolution:** implemented `OllamaProvider`, running `llama3.1:8b` locally — no key, no billing. PRD §14 explicitly permits an open-source model in place of an API, so this resolves that choice rather than working around it. The `LLMProvider` Protocol, `persona_service.py` and the response parser were all untouched; `AnthropicProvider` remains selectable via `LLM_PROVIDER`.

**A bonus the swap provided:** Ollama's `format` parameter accepts a JSON schema and constrains decoding, so the model *cannot* emit anything but `{reaction_text, purchase_likelihood}`. That is a stronger guarantee than the Anthropic path, which asks for the shape in the prompt and repairs the output afterwards.

**Measured:** ~2.6–3.4s per call warm (~49s on the first call while the model loads into VRAM).

### 8.2 Generative model: StyleGAN2 transfer learning → FastGAN from scratch

**Planned (Decisions #5/#6):** fine-tune a pretrained StyleGAN2 checkpoint, on a rented cloud GPU, because local hardware was assumed too weak to train from scratch.

**What happened — three attempts, all worse than their own starting point:**

| # | Configuration | Outcome |
|---|---|---|
| 1 | No regularisation, 512px, 3,014 images, lr 1e-3 | Discriminator domination (`d_loss` 0.0005). FID **262 → 466** |
| 2 | R1 γ=10, 256px, 25,023 images, lr 2.5e-3 | `g_loss` 0.75 → 17 → **NaN at step 154** |
| 3 | R1 γ=1 + gradient clipping, lr 5e-4 | Numerically healthy — and still FID **325 → 344 → 371 → 365** |

Attempt 3 settled it: stable, no NaN, and monotonically *worse* anyway. The script's own checkpoint selector reported `Best FID 324.99 at step 0` — the untouched pretrained checkpoint beat every fine-tuned one it produced.

**Diagnosis:** the obstacle was the **domain gap**, not hyperparameters. The only pretrained checkpoints available are faces (`ffhq-res256`) and cats (`afhqcat`), and a batch-4 loop cannot carry either to footwear.

**What changed:** 25,023 real product photos now existed (they didn't when Decision #6 was written) — well above the 100–4,000 range lightweight GAN architectures target. Training from scratch became both feasible *and* better, because it removes the domain gap entirely.

**Result:** FastGAN, trained from scratch, no pretrained weights. FID **380.9 → 287.7 at step 14,000**, 20,000 steps in ~2.5 hours locally.

```
step:  2000   4000   6000   8000  10000  12000  14000  16000  18000
FID:  380.9  388.0  356.7  370.3  354.0  322.0  287.7  328.0  327.8
                                                 ▲ best
```

Training is **not monotonic** — FID rose again after 14,000, which is exactly why interval checkpointing exists and why `GAN_CHECKPOINT` points at step 14,000 rather than the final checkpoint.

**Scope:** "GAN-centric" is preserved — one GAN architecture replaced another. The StyleGAN2 path remains working and selectable, so the superseded approach stays reproducible rather than deleted.

**Honest limitation:** output is recognisably footwear with laces, soles and realistic colourways, but roughly 20% of samples are malformed and none would pass for a product photo. Mature StyleGAN2 on a clean dataset scores FID in the single digits; we are at 288. That gap is compute, not a defect.

### 8.3 Persona prompts: raw metadata → shopper language

**Found by running the full user journey end to end for the first time with both a real GAN and a real LLM.**

`build_persona_reaction_prompt()` dumped `ProductVariant.attributes` into the prompt verbatim — and that dict is generator bookkeeping: `anchor_seed`, `perturbation_radius`, `generation_method`, and a note about latent-space perturbation. Personas were reacting to the *implementation*:

> *"I'm not impressed by this product design variant. The use of latent-space perturbation..."*

**Nothing errored**, which is precisely why it survived 67 passing tests: the pipeline ran, scores were produced, reports exported. But sentiment, risk, optimisation scoring, the PMF score and the final recommendation are *all* computed from that feedback — so the entire chain was grading reactions to jargon while appearing to work.

**Fix:** `describe_variant_for_persona()` renders only what a shopper could perceive — hue rotation becomes a named colourway, the 0-based index becomes "design variation 2", feedback-refined variants say so. Seeds and method names are dropped, because there is no shopper-meaningful version of them.

**After, same variant, live model:**
> Budget persona (0.10): *"I don't know if a green colourway is necessary... I'm happy with my current shoes"*
> Collector (0.60): *"Not too sure about this green-toned colourway, feels a bit too bold for my taste"*

Still differentiated — now about the product.

---

## 9. Notable bugs found and fixed

Recorded because each was invisible to code review and only surfaced by running the thing.

| Bug | How it hid | Consequence if shipped |
|---|---|---|
| **Placeholder product IDs** | CSV column named `source_product_id` matched none of the collector's aliases (`id`/`asin`/`sku`/…), so every row silently got `zappos-row-N` | Every downstream join — images, reviews, prices — would have been broken |
| **Footwear filter matched 0 products** | Every Amazon category path *starts* with the literal root "Clothing, Shoes & Jewelry", so a substring test for "jewelry" rejected everything, boots included | No training data at all |
| **Hand-loading the GAN produced garbage** | Every state-dict key matched, nothing raised, only non-persistent blur buffers were "missing" — and the model generated blue blobs on tan | Broken image generation, no error anywhere |
| **FastGAN output is unbounded** | Measured `[-2.40, 1.95]`, not `[0,1]`; applying StyleGAN2's `(img+1)/2` on top brightens every pixel | Washed-out variants |
| **Duplicate product IDs** | The ID registry issues one ID per fingerprint, so different ASINs for the same shoe collided; 3,334 IDs appeared more than once | 4,875 phantom duplicate rows |
| **Postgres 65,535-parameter cap** | One INSERT bound every row at once — fine for 4-row fixtures, 577K parameters at real scale | Ingestion crash |
| **CSV 128KB field limit** (×2) | `master_products.csv`'s JSON reference arrays exceed Python's default field cap | Stage 7 and the ingest script both crashed |
| **A test that couldn't fail** | A regression test for the rescale bug **passed with the bug deliberately injected** — a wide output range saturates both ends either way | False confidence; caught only by mutation-testing the test |
| **`num_workers` default** | `lightweight-gan` defaults it to `None`, making JPEG decode — not the GPU — the bottleneck | **4.55 s/step vs 0.45 s/step**: a 22-hour run instead of 2.4 hours |

Four defects in the `lightweight-gan` package itself were worked around and documented at the call site: `use_aim=True` crashes because its own `ImportError` handler still dereferences the missing module; `num_train_steps` falls through `**kwargs` into a model that rejects it; `calculate_fid_every=0` raises `ZeroDivisionError` instead of disabling; and a lazily-imported `pytorch_fid` **killed a 2.5-hour training run at step 2,000**. Evaluation failures are now non-fatal and `--resume` exists.

---

## 10. Testing

**78 automated tests**, all passing.

| File | Tests | Covers |
|---|---|---|
| `test_gan_inference.py` | 9 | Variant generation, FastGAN adapter contract |
| `test_prompt_templates.py` | 9 | Jargon-leak guard, hue wrap-around, malformed input |
| `test_llm_provider.py` | 8 | Schema enforcement, error mapping, live integration |
| `test_optimization_service.py` | 7 | Scoring, stopping criteria |
| `test_products.py` | 7 | Upload validation, ownership scoping |
| `test_auth.py` | 6 | Registration, login, token rejection |
| `test_risk_service.py` | 6 | Each risk rule |
| `test_dashboard.py` | 5 | Aggregation |
| `test_recommendation_service.py` | 5 | Ranking, normalisation |
| `test_ingestion.py`, `test_persona_service.py` | 4 each | Pipeline ingest; per-pair failure isolation |
| `test_admin.py` | 3 | Role enforcement |
| `test_sentiment_service.py` | 2 | Classification |
| `test_e2e_pipeline.py` | 1 | Full journey (mocked externals) |

**A limitation worth stating plainly:** every automated test mocks the GAN and the LLM. That is deliberate — real calls would make CI slow, expensive and non-deterministic — but it is exactly why §8.3's bug survived 67 passing tests. Mocked tests prove orchestration; only a real run proves the system does the right thing.

Tests that touch a live service (`test_llm_provider.py`'s integration case) **skip** when it is unavailable rather than fail, since Ollama shares the same 6GB GPU as the GAN tests and errors under contention. An unavailable external service is not a defect in our code.

### Manual full-journey verification

Run once with **real GAN and real LLM together**, through the real UI in a real browser:

| Step | Result |
|---|---|
| Register → Login → Dashboard | ✅ 0 console errors, 0 failed requests |
| Upload product | ✅ stored, preprocessed, rendered |
| Simulation | ✅ completed, 2 iterations, 6 variants |
| Persona reactions | ✅ **29 of 30 genuine** (1 error row, correctly isolated) |
| Recommendation + analytics | ✅ PMF score, full breakdown |
| Report export | ✅ PDF 2.7KB, CSV 12.9KB |

---

## 11. Running the system

```bash
# 1. Database (detached; already running is fine)
docker compose up -d db

# 2. Backend — from backend/, venv active
uvicorn app.main:app --reload        # http://localhost:8000  (docs at /docs)

# 3. Frontend — from frontend/
npm run dev                          # http://localhost:5173
```

Also required for persona simulation: **Ollama** running `llama3.1:8b` (`ollama list` to confirm). It installs as a background service.

First-time setup: `python -m venv .venv`, `pip install -r requirements.txt`, copy each `.env.example` to `.env`, `alembic upgrade head`, `python -m scripts.seed_personas`, `npm install`.

Admin access is operational-only — promote an existing account via `auth_service.promote_to_admin()`; there is no admin signup route by design.

---

## 12. Current state and what remains

**Working:** authentication, product upload, scenario configuration, GAN generation, persona simulation, sentiment, risk detection, the optimisation loop, recommendations, dashboard, report export, and the full React UI. 730,713 real reference rows in Postgres. 78 tests passing.

**Not done:**
- **Cloud deployment (Step 42)** — `render.yaml` and a full runbook exist and were locally verified, but no live deploy has been performed.
- **Production verification (Step 43)** — depends on the above.
- **Phase 17 optional enhancements** — FAISS/RAG grounding over the 496,592 real reviews, Celery+Redis async queue, dynamic LLM-authored personas, MLflow tracking. None are required for certified scope.

**Known limitations, stated rather than hidden:**
- GAN output is recognisable but not photorealistic; this is compute-bound, with the FID curve as evidence.
- Small-sample FID against a single product's reference images is a rough signal, not a benchmark.
- Persona-response consistency variance can be high (one sampled re-run measured 1.000), the expected behaviour of a temperature-0.8 8B model — surfaced as a reliability signal rather than tuned away.
- The trained model weights exist only on the development machine; they are excluded from version control (~11GB) and retraining is stochastic.
- A deployed instance cannot reach `localhost:11434`, so production would need either an Anthropic key or a hosted Ollama.

---

*Report generated 2026-09-24, reflecting commit `aca148d`.*
