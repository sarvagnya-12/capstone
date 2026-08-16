# PROJECT_CONTEXT.md — DryRunAI

Dense technical context for Claude Code sessions. Companion document: `PRD.md` (same directory) — read that for full detail/tables; this file is the compressed version for fast session start.

## Provenance

Reconstructed from 5 documents in `Capstone Docs/`: `t6.pdf` (certified Phase-1 report — **highest authority**), `Synopsis capstone.pdf` and `syn1.docx (1)_removed.pdf` (early-phase subsets of t6.pdf), `Lit_Review.pdf` (working doc with 4 architecture diagrams, **not certified**, more technically detailed than the SRS), `Lit_Review_Papers - Sheet1.pdf` (44-paper survey spreadsheet). The dataset-extraction pipeline at `Capstone Dataset/DryRunAI/` (catalog builder, asset manager, review builder, market/product-intelligence/knowledge-integration/dataset-quality services) is **out of scope** — it is only the upstream data source the core system consumes; do not analyze or modify it under this context.

Tags used below: **[CONFIRMED]** = in certified `t6.pdf`. **[PROPOSED]** = SRS lists as one of several options. **[WORKING]** = only in `Lit_Review.pdf`, not certified. **[OPEN]** = unresolved/contradictory — do not silently pick an answer.

## Purpose / Core Problem

DryRunAI is a proposed pre-launch product simulation platform for **organisations** (not consumers). Problem: 70–80% of new products fail post-launch because traditional validation (surveys, focus groups, A/B/beta testing) is slow, biased, small-sample, and mostly happens *after* launch. DryRunAI's premise: generate synthetic product-design variants with a GAN, simulate customer reactions with LLM-driven personas, score sentiment/risk/engagement, and iteratively refine toward a recommended launch variant — all before real-world deployment. **[CONFIRMED]**

**Status: 100% design-stage.** Nothing described anywhere in the source material is implemented. This is a Phase-1 academic capstone report (SRS + architecture + literature survey), not a working-system status report. Treat every component below as PLANNED unless stated otherwise.

## Goals

Generate controlled GAN variants (colour/texture/layout/packaging/branding) → simulate audience reaction via LLM personas → detect sentiment/risk → optimise iteratively → recommend best variant. Target industries: e-commerce, consumer goods, fashion, SaaS, marketing agencies, retail, start-ups. **[CONFIRMED]**

## Documented Pipeline (7 stages)

Product Input → GAN-Based Product Generation → Scenario Configuration (pricing/demographic/messaging) → LLM-Based Audience Simulation → Sentiment & Risk Analysis → Feedback-Driven Optimisation → Final Recommendation. **[CONFIRMED — t6.pdf §1.6]**

Note: the Activity Diagram sequences Scenario Configuration *before* Generation, while the prose stage list numbers it 3rd (after Generation) — minor internal inconsistency, not resolved; the diagram ordering is more likely to be intended.

Loop: after Final Recommendation, an activity-diagram decision ("More Iterations?") can send the flow back to Scenario Selection. **No stopping criteria are documented** (no score threshold / max-iterations / convergence rule). **[OPEN]**

## Architecture — two versions, do not conflate

**Certified 7-layer (t6.pdf, authoritative):** UI Layer → Application Layer → GAN Processing Layer → LLM Persona Layer → Optimisation Layer → Database Layer → Analytics Dashboard Layer.

**Working "Phase 3 Advanced" architecture [WORKING, `Lit_Review.pdf`, not certified — more detailed but not formally adopted]:** React/Streamlit UI → FastAPI Gateway (+ Celery async queue, Redis cache) → Data Ingestion/Preprocessing (CNN image embeddings, BERT/Sentence-Transformer text embeddings) → Vector KB (FAISS/Weaviate: product/persona/scenario embeddings) → Generative Design Engine (StyleGAN + Stable Diffusion) → Persona Simulation Engine (GPT/LLaMA/Mistral, RAG-style context injection) → Multi-Agent Simulation Layer (LangChain/CrewAI: Persona Agent, Market Analyst Agent, Risk Analysis Agent, Supervisor Agent that resolves conflicts) → Feedback Optimization Loop (Bayesian optimization + genetic algorithms) → Visualization Dashboard → Model Ops (Docker/Kubernetes serving, MLflow/Weights & Biases tracking).

**The gap between these two matters**: vector DBs, agent frameworks, Celery/Redis, and MLOps tooling appear *only* in the working doc, never in the certified SRS. Before building any of that, confirm with the team/guide whether Phase 3 has been adopted as actual scope or is still exploratory — it is meaningfully larger than what was formally submitted.

## Components (functional requirements, certified)

Authentication · Product Upload · Scenario Configuration · GAN-Based Product Generation · Persona Simulation · Sentiment Analysis · Risk Detection · Feedback Optimisation · Dashboard · Final Recommendation. Class model: `User`, `Product`, `Simulation`, `Persona`, `Feedback`, `Recommendation`, `Admin` — User uploads Product; Product used in Simulation(s); Simulation uses Persona(s) and generates Feedback; Feedback → Recommendation; Admin manages Users/monitors Simulations. **[CONFIRMED]**

## AI/ML Architecture

- **GAN**: variant generation. Survey covers StyleGAN/StyleGAN2/DCGAN/CGAN/CycleGAN/Pix2Pix/InfoGAN/BigGAN; architecture diagrams select StyleGAN, Phase 3 also lists **Stable Diffusion** (a diffusion model, not a GAN) — tension with the project's "GAN-centric" title/framing. **[OPEN]**
- **LLM persona engine**: "APIs / Open-source LLMs" per SRS **[PROPOSED — either is allowed, OpenAI or HuggingFace explicitly named as options]**; GPT/LLaMA/Mistral per working doc. **Note: this project's own SRS permits LLM API usage — do not apply a blanket "no external APIs" rule here unless the user says otherwise for this project.**
- **Multi-agent orchestration** (LangChain/CrewAI): **[WORKING only]**, not certified.
- **Sentiment/Risk**: NLP sentiment classification (pos/neg/neutral) + rule-based/anomaly risk detection. No specific model named. **[CONFIRMED]**
- **Vector KB** (FAISS/Weaviate): **[WORKING only]**, not certified.
- Nothing above has a stated training approach — see Training Strategy below.

## Persona Architecture — [OPEN, important]

Predefined, prompt-engineered profiles (age/income/preferences/behaviour) — **[CONFIRMED]** current scope is explicitly "public datasets and predefined personas" (proof-of-concept). Only 2–3 example personas ever appear concretely across all diagrams (e.g., price-sensitive student, urban professional, trend-driven buyer / student, budget shopper, premium user). The literature survey cites *related work* on population-aligned and dynamically-refined persona generation, but **no document confirms DryRunAI implements either**. **How the system is meant to avoid being limited to a handful of fixed personas is genuinely unresolved** — treat as a first-order design decision, not a detail to infer.

## Product Generation Architecture

Attributes varied: colour/texture/layout/presentation style (abstract) or colour/packaging/layout/aesthetics/branding (SRS body) — overlapping lists, not formally unified. No fixed-vs-variable attribute split documented. No variant-count target (diagrams use placeholder "N"). **No realism metric (FID/IS/human-eval) or diversity metric documented anywhere** — open and important before generation-quality claims can be made. **[OPEN]**

## "Market Simulation" — thinner than the subtitle implies

No standalone demand/pricing/competitor model exists. What's documented: a Scenario Configuration module (pricing/demographic/messaging as inputs), an unelaborated "Market Reactions Simulation" box (Phase 1) and "Market Analyst Agent" (Phase 2/3) **[WORKING only]**. "Product-market fit score" appears to be computed as an **aggregate of persona sentiment/engagement/purchase-intent**, not output of a distinct economic simulation. **[OPEN]** whether a real market-dynamics layer is intended.

## Optimization Loop — [OPEN, CRITICAL]

The loop is Generate → Simulate → Evaluate → Optimise → (repeat). **The optimisation mechanism is described inconsistently across every source that mentions it**:
- Abstract/synopses: latent-space manipulation + hyperparameter tuning + scenario weighting + threshold-based risk scoring (no RL, no Bayesian/genetic).
- SRS functional-requirements table: "Reinforcement learning / feedback loop optimization" (implies RL is current).
- SRS Scope section: lists RL optimisation explicitly as **future** work (implies RL is *not* current).
- Working architecture (Phase 2/3 diagram): Bayesian optimization + genetic algorithms (no RL in this box).
- Working simplified diagram: shows an explicit "RL Feedback Loop" box.

**Do not pick one of these and implement it as if settled — this must be clarified by the team before any optimisation code is written.** RL, Bayesian optimisation, and genetic algorithms are architecturally very different (reward/environment design vs. surrogate-model search vs. population search).

## Training Strategy — [OPEN, CRITICAL]

Not documented: whether GAN/diffusion models are trained from scratch, fine-tuned, or inference-only on pretrained checkpoints. Certified hardware spec is modest (i5/i7, 8GB RAM, 256GB SSD, "NVIDIA GPU recommended") **[CONFIRMED]**, in unresolved tension with the literature survey's own repeated notes that StyleGAN2/BigGAN-class models "demand extremely high computational resources." Only public datasets are permitted (Legal Feasibility, `t6.pdf` §5.6) — no private/proprietary data.

## Technology Decisions — mostly either/or, not finalized

Per certified SRS (Table 5.5), presented as **options, not commitments**: Frontend React or Streamlit · Backend FastAPI or Flask (FastAPI "preferred for performance") · DB MySQL or MongoDB · GAN framework PyTorch or TensorFlow · LLM via API or open-source · Cloud AWS/Azure/GCP. **[PROPOSED]**

Per working doc only, **not certified**: Celery + Redis (async/cache), FAISS/Weaviate (vector DB), LangChain/CrewAI (agents), Docker + Kubernetes (serving), MLflow + Weights & Biases (experiment tracking). **[WORKING]**

## Implementation Status

Everything above is **PLANNED / PROPOSED**. No code, trained model, or deployed service is described anywhere in the source documents. This is a design-and-literature-review deliverable (Capstone Phase 1), not a build-status report.

## Dataset Pipeline Interface (`Capstone Dataset/DryRunAI/`)

Separately maintained, read-only from the core system's perspective — do not analyze its internals beyond this interface summary, do not edit it. It is a 7-stage, deliberately **non-AI** ETL pipeline (its own README states: "No GAN, LLM, or API code is included") that produces a **footwear/sneaker-vertical** product catalog from public sources (Zappos, Nike, StockX). All 7 services are code-complete, but **no data has actually been generated yet** — `project_manifest.json` shows `dataset_health_score: 0` and every record count at `0`; only tiny hand-authored test fixtures (4 rows) exist under `datasets/`.

**Verified outputs and how they map onto the core system:**

- `master_products.csv/.parquet/.jsonl` (unified catalog: brand, model, category, colors, material, price, cross-references, provenance) + real downloaded product **image files** (`datasets/assets/.../images/*.jpg`, deduplicated/validated) → a genuine seed catalog and real image corpus the GAN could train/fine-tune on. Concrete answer to part of the undocumented training-data gap (Open Decision on training strategy).
- `reviews.csv` (real review text, ratings, verified-purchase flag, language) → maps almost exactly onto the working architecture's own "retrieve product review insights" RAG step in the Persona Simulation Engine (`Lit_Review.pdf` Phase 3) — a natural grounding/retrieval corpus for the LLM persona layer, and a real sentiment distribution to sanity-check simulated personas against.
- `product_intelligence.csv`'s target-segment fields (`target_age_min/max`, `target_gender`, `target_income_segment`, `target_region`, `target_lifestyle`, brand positioning/ambassador, competitor products/brands) → the closest thing either codebase has to real seed data for **persona generation** — could ground personas in actual brand-stated target segments instead of the 2–3 hand-picked examples in the diagrams. Supplies seed *facts*, not a generation mechanism — doesn't resolve the persona-diversity open decision, but gives it something real to work from.
- `market.csv` (real price/availability by market type/region) → grounds Scenario Configuration's pricing input in real ranges instead of arbitrary numbers; still a snapshot, not a demand/elasticity model.
- `taxonomy/` (colors, categories, materials, image types — controlled vocabularies) → directly reusable as the GAN's conditional-attribute label space and as UI dropdown options.
- `schemas/personas_schema.json`, `marketing_schema.json`, `simulation_schema.json` are **deliberately empty** (`"columns": []`) — as are `taxonomy/lifestyles.json` and `taxonomy/marketing_strategies.json`. This is a clean scope signal, not an oversight: the dataset team has reserved these contracts for the core AI team to define. Confirms the intended division of responsibility (factual data = pipeline's job; personas/marketing/simulation = core system's job).

**Caveats:**
- Currently footwear-only (category taxonomy, `DRY-SNK-` product-ID prefix, sneaker-specific sources) — useful as a single-vertical proof-of-concept, not evidence the multi-industry framing in the PRD already works end-to-end.
- No sentiment/inference exists anywhere in the pipeline by design — the core system must do its own sentiment/analysis work on the raw review text supplied, cannot rely on the pipeline for it.
- **No documented integration mechanics** connect the two codebases (no shared API, DB, or file-path convention for "core system reads `master_products.csv`") — see Open Decision #11 below.

## Terminology

- **Launch scenario** — a bundle of pricing/target-demographic/messaging parameters a variant is evaluated under.
- **Persona reasoning / persona simulation** — LLM-generated qualitative feedback + sentiment + purchase-likelihood from a simulated customer profile reacting to a product variant.
- **Product–market fit score** — an aggregate output metric combining persona-level sentiment/engagement/purchase-intent; not a distinct market-simulation output.
- **DryRun** — the core metaphor: testing a launch virtually ("dry run") before real-world commitment.
- **Variant** — one GAN/diffusion-generated synthetic product-design output.

## Things that MUST NOT be changed without explicit approval

- The "GAN-centric" framing/title of the project (per the certified report) — do not silently pivot the core narrative to "diffusion-centric" even though Stable Diffusion appears in the working architecture; that tension is an open decision, not a mandate to switch.
- Exclusion of the dataset-extraction pipeline (`Capstone Dataset/DryRunAI/*`) from core-system scope/analysis.
- The public-dataset-only / no-proprietary-data constraint (Legal Feasibility).
- Treating `Lit_Review.pdf`'s architecture as certified scope — it is the team's current thinking, not the formally submitted design, until confirmed otherwise.

## Open Decisions (priority-ordered — see PRD.md §37 for full detail)

1. **CRITICAL** — Optimisation-loop mechanism (RL vs. Bayesian/genetic vs. heuristic weighting).
2. **CRITICAL** — Persona diversity/scale mechanism (fixed set vs. dynamic/population-generated).
3. **CRITICAL** — Generative-model training strategy vs. stated hardware.
4. **HIGH** — "GAN-centric" branding vs. diffusion-model inclusion.
5. **HIGH** — Product-realism / persona-consistency evaluation methods (none defined).
6. **HIGH** — Iterative-loop stopping criteria (undefined).
7. **MEDIUM** — Depth of "market simulation" (aggregate persona metric vs. real market model).
8. **MEDIUM** — Authority gap between certified SRS architecture and working `Lit_Review.pdf` architecture.
9. **LOW** — Pipeline-stage ordering (Scenario Config before/after Generation).
10. **LOW** — Literature review's own per-member "Research Gaps" table is unfilled in the source doc.
11. **MEDIUM** — No documented mechanics for how the core system actually ingests the dataset pipeline's output (`master_products.csv`, images, reviews, market, product-intelligence) — no shared API/DB/file-path convention specified anywhere.
