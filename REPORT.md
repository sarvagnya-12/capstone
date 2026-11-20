# DryRunAI — Implementation Report

**A GAN-centric generative AI framework for pre-launch product simulation and product-market-fit optimisation.**
Academic capstone, BMS College of Engineering, Dept. of ISE, AY 2025–26.

This document records what was actually built, how it works, and — importantly — where the implementation departed from the original plan and why. Several of those departures were forced by measured failures rather than preference, and they are reported here with the evidence that drove them rather than quietly folded in.

Companion documents: [`PRD.md`](PRD.md) (requirements), [`IMPLEMENTATION.md`](IMPLEMENTATION.md) (step-by-step build plan and per-step status), [`GENERATOR_ALT.md`](GENERATOR_ALT.md) (the GAN-vs-diffusion analysis), [`TRAINING_TRANSFER.md`](TRAINING_TRANSFER.md) (running the large GAN training elsewhere), [`docs/deployment.md`](docs/deployment.md) (deployment runbook).

---

## 1. What the system does

A user uploads a product concept (image + description + branding) and describes a launch scenario (price, target customers, marketing message). The system then:

1. **Generates design variants** of that product. A hosted diffusion model renders each variant from the uploaded photo in a new colourway; an **ESRGAN upscaler the project trained itself** sharpens it to 1024 px. The project's FastGAN generator is the fallback when a render fails, and the baseline the renders are measured against.
2. **Simulates customer reactions** by showing each variant's image to a vision-capable language model that role-plays a library of predefined customer personas, grounded in real reviews of similar shoes.
3. **Analyses that feedback** — sentiment classification, rule-based risk detection.
4. **Optimises** — scores variants, nudges the next round toward better-performing colours, and repeats for a bounded number of iterations.
5. **Recommends** the best variant and explains the result in business terms — how many customer profiles would buy it, who it appeals to, what they objected to, and what to do next — on a dashboard and as a PDF/CSV report.

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
| ML runtime | PyTorch (CUDA 12.6) | 2.13.0 |
| GAN generator (baseline / fallback) | FastGAN via `lightweight-gan`, trained from scratch | 1.2.1 |
| GAN upscaler | ESRGAN (RRDBNet + U-Net discriminator), implemented and trained from scratch | — |
| Image rendering | Cloudflare Workers AI, FLUX.2 Klein 4B (hosted; free daily allowance) | — |
| Image rendering (alternative) | Google Gemini image models (adapter written; needs billing) | — |
| Realism metric | `torchmetrics` FID + `pytorch-fid` | 1.9.0 / 0.3.0 |
| Sentiment | HuggingFace `transformers` | 5.15.0 |
| Review search | `sentence-transformers` (`all-MiniLM-L6-v2`) | 6.1.0 |
| Persona model | `gemma4:31b-cloud` through Ollama Cloud (vision) | — |
| Persona model (alternatives) | local Ollama (`llama3.1:8b`), Anthropic SDK | 0.34.3 / 0.122.0 |
| Auth | `python-jose` (JWT) + `passlib`/`bcrypt` | 3.5.0 / 4.0.1 |
| Reports | ReportLab | 5.0.0 |
| Containerisation | Docker Compose (Postgres + backend + nginx frontend) | — |

**Development hardware:** Windows 11, NVIDIA RTX 4050 Laptop GPU (6 GB VRAM), 15.6 GB RAM. The VRAM ceiling shaped several decisions recorded below.

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
   sentiment · risk · optimization · recommendation · insights · report
                    simulation_orchestrator
                                │
        ┌───────────────┬───────┴────────┬──────────────────┐
        ▼               ▼                ▼                  ▼
   ML modules       PostgreSQL     Local filesystem    Hosted APIs
 gan/ sr/ diffusion/ app tables +   products, GAN and   Cloudflare (images)
 llm/ nlp/ retrieval/ ref_* corpus  ESRGAN weights,     Ollama Cloud (personas)
                                    review index
```

### Request flow for a simulation

`POST /api/v1/simulations` validates the scenario, creates the row, and returns **202 Accepted** immediately, dispatching `simulation_orchestrator.run()` to a FastAPI `BackgroundTask`. The client polls `GET /simulations/{id}/status`. The orchestrator then loops:

```
generate variants   (FastGAN candidates → diffusion render from the product photo
                     → ESRGAN 2× upscale; FastGAN image kept if a render fails)
   → score realism (FID)
   → persona reactions (vision LLM, one call per persona × variant, image attached,
                        5 real reviews of similar shoes in the prompt)
   → sentiment classification
   → risk detection
   → optimisation scoring
   → stop? (max iterations OR PMF plateau)  ── no ──▶ nudge colour/latents, repeat
                                             └─ yes ─▶ build recommendation
```

The generator is chosen by `GENERATOR_BACKEND` (`gan` or `hybrid`); everything after generation is identical for both. A two-variant, one-round simulation on the hybrid pipeline took 135 s end to end.

---

## 4. Data model

Eight application tables plus five read-only reference tables:

| Table | Purpose |
|---|---|
| `users` | Accounts; `role` enum (`user`/`admin`) |
| `products` | Uploaded concepts, image paths |
| `product_variants` | Generated variants; `attributes` JSONB (requested colour, generation method, upscaling, render errors), `fid_score` |
| `simulations` | Scenario config, status enum, iteration counters |
| `personas` | Predefined persona library (20 seeded) |
| `simulation_personas` | Many-to-many association |
| `feedback` | One row per persona × variant: text, purchase likelihood, sentiment, risk flags |
| `recommendations` | Final ranking, PMF score, summary |
| **`ref_products`** | Reference corpus from the dataset pipeline — **109,808** rows |
| **`ref_images`** | **46,272** |
| **`ref_reviews`** | **496,592** |
| **`ref_market`** | **36,096** |
| **`ref_product_intelligence`** | **41,945** |

Two deliberate deviations from the certified class diagram, both documented in code:

- **`ProductVariant` is an added entity.** The diagram implies it (FR#4 says "GAN generates synthetic variations") without naming it, but `Feedback` must reference a *specific* variant rather than the parent product.
- **`Admin` is a `role` column, not a table.** It reproduces the same relationships the diagram specifies without a redundant entity.

The `ref_*` tables carry **no foreign keys** into application tables — the pipeline's `product_id` namespace is separate from `products.id`. They are a queryable corpus, not a relational extension. The new pipeline needed **no migration**: generation details live in the `attributes` JSONB column.

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
| GET | `/simulations/{id}/analytics` | Dashboard data, including the business summary (`insights`) |
| GET | `/simulations/{id}/report?format=pdf\|csv` | Business report / spreadsheet |
| GET | `/admin/users`, `/admin/simulations` | Admin-only (403 otherwise) |

**Ownership leaks are treated as information disclosure:** requesting another user's resource returns **404, not 403**, so the API never confirms that an unowned resource exists.

---

## 6. Components in detail

### 6.1 Authentication
bcrypt password hashing (`passlib`), JWT access tokens (`python-jose`) carrying `sub` and `role`. No refresh-token flow — a single short-lived token satisfies the stated requirement without added complexity. Two dependencies, `get_current_user` and `get_current_admin_user`, guard every protected route.

**Admin promotion is deliberately not an API route.** `auth_service.promote_to_admin()` exists as an operational helper only; self-service promotion is a security hole no requirement asked for.

### 6.2 Product upload and preprocessing
Validates content type, extension whitelist and size *before* writing anything to disk — no orphaned files from rejected uploads. Images are normalised to RGB at 256×256 (`image_preprocessing.TARGET_SIZE`). Storage sits behind a two-function interface (`save_upload`, `get_path`) so object storage could replace the local filesystem without touching callers.

### 6.3 Variant generation
`gan_service.generate_variants_for_simulation()` is the single entry point; `GENERATOR_BACKEND` selects the path.

- **GAN path (`gan`, the default and the baseline).** `inference.generate_variants()` derives a deterministic anchor latent from the product ID, takes small perturbations around it, and applies an HSV hue shift for colourway variation. `load_generator()` dispatches on file extension: `.pt` → FastGAN, `.pkl` → StyleGAN2.
- **Hybrid path (`hybrid`).** The FastGAN still produces candidates, which carry the colour the optimiser requested and serve as the fallback image. Each variant is rendered by the hosted diffusion model **from the uploaded photo**, with a prompt built from the product's name, category, description and the requested colour (the brand is omitted — image models draw it as garbled lettering). The render is 512 px; the **trained ESRGAN upscales it to 1024 px**. A failed render, a safety-filter refusal after three re-seeded retries, or a spent per-simulation budget (`MAX_API_IMAGES_PER_SIMULATION`) keeps the FastGAN image for that variant and marks it `generation_method="gan"`; a simulation never fails because the API did.

Providers sit behind an `ImageProvider` Protocol mirroring the LLM provider layer: Cloudflare Workers AI (FLUX.2 Klein 4B, in use) and Gemini (written; its free tier allows no image requests). Adding another provider is one class.

### 6.4 Realism scoring (FID)
FID is a **set-vs-set** statistic, so all variants from one generation batch share a single score — "one image's FID" is not a meaningful quantity, and this is stated in code rather than silently assumed. Returns `None` rather than a misleading `NaN` when the sample is too small (< 2 images). Small-sample FID against a single product's own reference images is a rough signal, not a benchmark. For orientation: hybrid variants of a sneaker scored 60.7 in an end-to-end run, where FastGAN-only variants typically score above 270 — on different reference sets, so not a strict comparison.

### 6.5 Persona simulation
20 seeded personas spanning lifestyle (Budget Shopper, Premium User, Athletic/Active, Trend-driven, Family-focused, …), income segment, region (US/EU/APAC) and age band. For each persona × variant, a prompt is built and sent to the persona model; the structured reply becomes a `Feedback` row. The prompt contains:

- **the product** (brand, name, category, description) — before 2026-10 personas were told only "design variation 2", without knowing it was a shoe;
- **the variant image** (`LLM_VISION`), so personas react to what the design looks like;
- **five real reviews of similar shoes** (`REVIEW_GROUNDING_ENABLED`), labelled as reference material written about other brands, never to be copied;
- the launch scenario (price, target customers, message).

**Failures are isolated per pair:** one failed call records an `[LLM_ERROR]`-marked row and the simulation continues. `check_consistency()` re-runs a sample of pairs and records how far the output drifts, as an evaluator-reliability signal.

**Review search.** 349,752 usable reviews (≥ 60 characters after HTML clean-up, of 496,592) are embedded once with `all-MiniLM-L6-v2`. Per persona, retrieval takes the 3,000 reviews most relevant to the product, re-ranks them by the persona's own behaviour description, and picks 2 negative, 1 mixed and 2 positive reviews — the corpus is 64% five-star, so plain similarity would ground every persona in praise. Exact search over the matrix takes ~0.06 s, so no vector database was needed.

### 6.6 Sentiment, risk, optimisation, recommendation
- **Sentiment** — a HuggingFace transformer classifies each reaction. It measures the **tone of the comment**, not purchase intent, and is presented that way (positive / neutral / critical).
- **Risk** — rule-based flags (high critical-comment ratio, low purchase likelihood, unreliable persona signal, poor realism).
- **Optimisation** — weighted score over mean sentiment, mean purchase likelihood, and an engagement proxy. Stops on max-iterations **or** PMF plateau, whichever comes first.
- **Recommendation** — ranks variants and stores a 0–100 PMF score normalised across the variants of one simulation (so the best is always 100), plus a summary.

### 6.7 Business-facing results
`insights_service.build_insights()` restates a completed simulation for a product or marketing lead, and is the single source for the dashboard, the PDF and the CSV, so they never disagree:

- a **verdict** ("strong launch candidate" / "promising but needs refinement" / "none of the options is launch-ready yet") and a short bottom line;
- the **average purchase likelihood** as a real percentage, and **"N of M customer profiles would likely buy"** (≥ 60%) — the normalised PMF score is not shown to business readers, because it rated an option 100 when its average purchase likelihood was 37%;
- who each option appeals to and who is least interested, topics customers raised (price, comfort, quality, look, everyday use), concerns in plain sentences (including a price-objection check), the most positive and most critical quote, and next steps;
- colourways named from the **pixels of the generated image** — the requested colour is not always what the model drew (a black sneaker requested in its "original colourway" came back light grey);
- a disclaimer that the customers are simulated and the result is directional.

If the system recommends an option whose purchase likelihood is lower than another's (its ranking also weighs sentiment and risk), the summary says so and why, rather than appearing to contradict itself. The thresholds are presentation choices, not calibrated against real sales.

### 6.8 Frontend
Seven pages (`Login`, `Register`, `ProductUpload`, `ScenarioConfig`, `SimulationRun`, `Dashboard`, `Admin`). The results page shows the verdict, what was tested, a comparison table, one card per option (purchase-likelihood figure, labelled bars for buying intent and comment tone, appeals/concerns/quotes, all reactions on demand) and next steps; the earlier sentiment pie chart and 0–100 gauge were replaced because neither could be read without explanation. Auth lives in a React Context; a thin `apiFetch<T>()` wrapper centralises JSON handling, error unwrapping and the JWT header. `AuthenticatedImage` exists because images are auth-gated: a plain `<img src>` can't send a bearer token, so it fetches as a blob and renders an object URL.

---

## 7. The dataset pipeline

An archived, separately-built 7-stage ETL pipeline ships with the project. It was **code-complete but had never produced a single record** — `project_manifest.json` showed every count at zero.

**The key discovery on picking it up: it was never a scraper.** Class names like `NikeCollector` and `AmazonReviewCollector` imply live collection, but every one of them is a local-file parser. Nothing in the pipeline makes an HTTP request except the image downloader. Populating it therefore meant building an *acquisition layer*, not "running the pipeline".

Sources used, all public and legitimate — **no brand or retail site is scraped**:
- **UT-Zappos50K** — 50,025 catalog images (academic-use licence)
- **Amazon Reviews 2023** (McAuley Lab, via Hugging Face) — reviews and product metadata, streamed and filtered rather than downloaded whole
- **Wikipedia / Wikidata public APIs** — brand facts

Final output: **109,808 products, 46,272 images, 496,592 reviews, 36,096 price records, 41,945 brand-intelligence rows** — 730,713 rows ingested into the `ref_*` tables with **zero broken references and zero orphans**. The same Amazon metadata supplied the GAN training corpus (281,589 images at 256 px) and the ESRGAN training set (19,813 images at 512 px), downloaded from the `hi_res` URLs and padded, not cropped, to square.

### A note on the pipeline's own quality score

`project_manifest.json` reports `dataset_health_score: 17`, and five of six per-dataset scores are `0`. **That number is a scorer artifact, not a verdict on the data.** The scorer subtracts a *fixed penalty per row* with no normalisation and a floor of zero — it had only ever run against 4-row fixtures. 24,534 products with no matching review is −49,068 points on its own. Any real-scale dataset scores 0 under it.

What the underlying reports actually show: **0 duplicate IDs, 0 broken references, 0 schema violations** across all six datasets. The only missing-required field is `source_url` on the 24,522 Zappos products, which that dataset simply doesn't provide.

---

## 8. Major changes during implementation

This section is the reason this document exists. Each departure from the plan below was forced by measurement.

### 8.1 LLM provider: Anthropic API → local Ollama

**Planned:** Anthropic's API as the persona-reasoning engine.

**Problem:** no real LLM call had ever succeeded — with no API key configured, every `Feedback` row (60 of 60) carried an `[LLM_ERROR]` placeholder. A Claude subscription does not include API usage; the API bills separately per token.

**Resolution:** `OllamaProvider`, running `llama3.1:8b` locally — no key, no billing. PRD §14 explicitly permits an open-source model. The `LLMProvider` Protocol, `persona_service.py` and the parser were untouched; `AnthropicProvider` remains selectable. Ollama's `format` parameter constrains decoding to the reaction schema. Measured: ~2.6–3.4 s per call warm. (Superseded in part by §8.6.)

### 8.2 Generative model: StyleGAN2 transfer learning → FastGAN from scratch

**Planned (Decisions #5/#6):** fine-tune a pretrained StyleGAN2 checkpoint on a rented cloud GPU.

**Three attempts, all worse than their own starting point:**

| # | Configuration | Outcome |
|---|---|---|
| 1 | No regularisation, 512px, 3,014 images, lr 1e-3 | Discriminator domination (`d_loss` 0.0005). FID **262 → 466** |
| 2 | R1 γ=10, 256px, 25,023 images, lr 2.5e-3 | `g_loss` 0.75 → 17 → **NaN at step 154** |
| 3 | R1 γ=1 + gradient clipping, lr 5e-4 | Numerically healthy — and still FID **325 → 344 → 371 → 365** |

**Diagnosis:** the **domain gap**, not hyperparameters — the only pretrained checkpoints are faces and cats. With 25,023 real product photos available, training from scratch became feasible and better.

**Result:** FastGAN from scratch, FID **380.9 → 287.7 at step 14,000** (20,000 steps, ~2.5 h locally). It was later retrained on 150,031 images; the shipping checkpoint `shoes150k/model_20.pt` scores **FID 274.0** against a common 256-image reference set (a different reference from the 287.7, so the two are not directly comparable).

**Honest limitation:** output is recognisably footwear, but roughly 20% of samples are malformed and none would pass for a product photo. Variants were also random draws from the footwear distribution, not variants *of the uploaded product* — the uploaded photo only served as the FID reference. Both problems led to §8.4.

### 8.3 Persona prompts: raw metadata → shopper language

Found by the first end-to-end run with a real GAN and a real LLM: `build_persona_reaction_prompt()` dumped generator bookkeeping into the prompt, and personas reacted to the implementation ("The use of latent-space perturbation…"). Nothing errored, so 67 passing tests missed it — yet sentiment, risk, scoring and the recommendation were all computed from that feedback. **Fix:** `describe_variant_for_persona()` renders only what a shopper could perceive.

### 8.4 Image generation: FastGAN only → hosted diffusion rendering

**Problem.** §8.2's two limitations. They were analysed in [`GENERATOR_ALT.md`](GENERATOR_ALT.md), which recommended keeping the GAN and adding diffusion behind a switch.

**Provider.** Gemini's image models were tried first; the key's free tier allows **0** image requests, so they need billing. Cloudflare Workers AI's FLUX.2 Klein 4B runs within a free daily allowance (10,000 neurons, ~37 per 512 px render) and was adopted. Two practical findings: its output safety filter refuses ordinary shoe photos at random (about a quarter of renders; one adidas product 100%), so refusals are retried with new seeds; and brand names in the prompt come back as garbled lettering on the shoe, so the brand is left out.

**Does the GAN concept steer the render?** The plan was for FastGAN concepts to be the starting images ("GAN explores, diffusion renders"). `scripts/compare_diffusion_strength.py` tested it on 4 held-out real products × 5 GAN concepts × 3 strengths, against renders from the product photo alone:

| Starting image | Rendered | Refused | Outline similarity to GAN concept | to product | Looks like product (VGG) |
|---|---|---|---|---|---|
| GAN concept @ 0.30 | 15 | 5 | 0.598 | 0.907 | 0.835 |
| GAN concept @ 0.55 | 15 | 5 | 0.605 | 0.908 | 0.816 |
| GAN concept @ 0.85 | 13 | 7 | 0.586 | 0.919 | 0.823 |
| **Product photo only** | 15 | 5 | **0.589** | 0.925 | 0.827 |

The photo-only renders never saw the GAN concept, yet resemble it just as much: **the concept has no measurable effect**, and the sample grids look the same by eye. The renders keep the product's design (stitching, zips, logos, straps) and change the colourway realistically — fixing both of §8.2's limitations.

**Decision.** Renders start from the product photo (`DIFFUSION_INIT=product`). The project's GAN contribution to the delivered image is the upscaler (§8.5); the FastGAN remains the fallback and the baseline. "GAN-centric" is preserved by two GANs trained from scratch, and the claim that the FastGAN seeds the render is not made, because the measurement contradicts it. Pretrained models are now used outside the GANs (the hosted image and persona models; VGG19 inside the ESRGAN loss only), which needs the guide's sign-off against the public-data constraint (PRD §5.6).

### 8.5 A trained ESRGAN upscaler

An ESRGAN (RRDBNet generator, spectral-norm U-Net discriminator, L1 + VGG19 perceptual + adversarial loss) was implemented in PyTorch — `basicsr` is incompatible with the installed torchvision — and trained from scratch on **19,813 real 512 px shoe photos**, with synthetic blur, noise and JPEG so it learns realistic inputs. 15,000 L1 steps then 35,000 GAN steps at batch 16 on the local GPU (measured 0.19 s/step in the L1 phase and ~0.65 s/step in the GAN phase when the machine was otherwise idle; the run crashed once at step ~9,000 and was resumed from the step-5,000 checkpoint).

| Held-out photos (100) | PSNR ↑ | SSIM ↑ | VGG distance ↓ |
|---|---|---|---|
| Bicubic | 29.67 | 0.869 | 6.21 |
| ESRGAN, end of L1 phase (step 15,000) | 31.46 | 0.886 | 6.01 |
| **ESRGAN, final (step 50,000)** | 30.91 | 0.881 | **4.46** |

The GAN phase traded 0.5 dB of PSNR for a 26% better perceptual score — the intended ESRGAN trade of pixel accuracy for realistic texture. Both measures were still improving at the last step.

On **FastGAN output** it improved FID against real photos from 274.8 to 251.3, but it also sharpens the FastGAN's checkerboard artefacts, which become more visible. On **diffusion renders** — clean and photo-like, the kind of input it was trained on — it sharpens material texture without artefacts, which is where it is used: every 512 px render is upscaled to 1024 px, at a third of the API cost of rendering 1024 px directly.

### 8.6 Personas that see the variant and know real reviews

Local `llama3.1:8b` reactions were generic and could not respond to images. `scripts/compare_persona_prompts.py` measured the same 5 personas × 3 variants under each prompt setup, each prompt sent twice:

| `gemma4:31b-cloud` | baseline | + product | + reviews |
|---|---|---|---|
| Similarity between personas (lower = more distinct) | 0.456 | **0.374** | 0.412 |
| Concrete product aspects per reaction | 1.13 | 1.33 | **2.13** |
| Similarity to real reviews | 0.572 | 0.644 | 0.635 |
| Purchase-likelihood drift on re-run | 0.03 | 0.04 | 0.04 |
| Copied reviews / brand leaks | 0 / 0 | 0 / 0 | 0 / 0 |

Compared with local `llama3.1:8b` on the same test, gemma4 kept personas more distinct (baseline 0.456 vs 0.668) and more stable (drift 0.03–0.04 vs 0.08–0.14), and did not inflate purchase likelihood as context was added (llama rose from 0.47 to 0.64). The hosted model runs on Ollama Cloud's free tier.

With the image attached, **every persona rated the old FastGAN-only variants 0.0** ("it looks like an ink blot rather than a running shoe") — vision works, and it made plain that the GAN-only images could not support the simulation. On hybrid variants, personas react to what they see ("the light grey tone is clean, but I'm concerned about the durability of that mesh upper").

### 8.7 Results written for business readers

The dashboard and reports showed FID, an engagement proxy, internal rule names, IDs and raw JSON, and a 0–100 "PMF score" normalised so the best option is always 100 — it rated an option 100 whose average purchase likelihood was 37%. The sentiment pie chart showed counts without saying what they meant. §6.7 describes the replacement; two corrections matter beyond presentation: sentiment is shown as comment tone, because a customer can be critical in tone and still likely to buy; and colourways are named from the image's pixels, because the requested colour was not always what the model drew.

---

## 9. Notable bugs found and fixed

Recorded because each was invisible to code review and only surfaced by running the thing.

| Bug | How it hid | Consequence if shipped |
|---|---|---|
| **Placeholder product IDs** | CSV column named `source_product_id` matched none of the collector's aliases, so every row silently got `zappos-row-N` | Every downstream join broken |
| **Footwear filter matched 0 products** | Every Amazon category path *starts* with "Clothing, Shoes & Jewelry", so a substring test for "jewelry" rejected everything | No training data at all |
| **Hand-loading the GAN produced garbage** | Every state-dict key matched, nothing raised | Broken image generation, no error anywhere |
| **FastGAN output is unbounded** | Measured `[-2.40, 1.95]`, not `[0,1]` | Washed-out variants |
| **Duplicate product IDs** | One ID per fingerprint collided across ASINs | 4,875 phantom duplicate rows |
| **Postgres 65,535-parameter cap** | One INSERT bound every row at once | Ingestion crash |
| **CSV 128KB field limit** (×2) | JSON reference arrays exceed Python's default field cap | Stage 7 and ingest both crashed |
| **A test that couldn't fail** | A regression test **passed with the bug deliberately injected** | False confidence |
| **`num_workers` default** | JPEG decode, not the GPU, was the bottleneck | 22-hour run instead of 2.4 hours |
| **Review retrieval ignored the persona** | Product and persona in one query; the product text dominated | 8 lifestyles shared 3.8 of 5 reviews (fixed: 1.6) |
| **Even split reported as "mostly critical"** | Threshold used ≥ half instead of > half | Misleading verdicts on small samples |
| **Colour named from the request, not the image** | The model sometimes drew a different colour | Labels contradicting the picture |
| **Test suite read the developer's `.env`** | Fine until `.env` enabled the hybrid pipeline | Tests made real API calls and spent free quota; now every test pins defaults and blanks keys |
| **Training crash: host RAM** | ESRGAN ran alongside the test suite and an index build on 15.6 GB RAM | `cuDNN HOST_ALLOCATION_FAILED` at step 9,000; recovered with `--resume` |

Four defects in the `lightweight-gan` package itself were worked around and documented at the call site.

---

## 10. Testing

**160 automated tests** — 159 pass and 1 is skipped (the live Ollama integration test skips when no local server answers).

| File | Tests | Covers |
|---|---|---|
| `test_diffusion_provider.py` | 26 | Cloudflare/Gemini request format, retries, safety-filter re-seeding, zero-quota and auth errors |
| `test_persona_grounding.py` | 21 | Product/image/review prompts, image passing, rating-balanced retrieval, fallbacks |
| `test_sr.py` | 16 | ESRGAN shapes, degradation, train/val split, upscale wiring and target size |
| `test_prompt_templates.py` | 11 | Jargon-leak guard, hue wrap-around, malformed input |
| `test_insights.py` | 10 | Business wording, counts, colour naming, no internals in reports |
| `test_hybrid_generation.py` | 9 | Hybrid generation, fallback to GAN, API budget, seed selection |
| `test_gan_inference.py` | 9 | Variant generation, FastGAN adapter contract |
| `test_llm_provider.py` | 8 | Schema enforcement, error mapping, live integration |
| `test_products.py`, `test_optimization_service.py` | 7 each | Upload validation, ownership; scoring, stopping criteria |
| `test_auth.py`, `test_risk_service.py` | 6 each | Registration, login, tokens; each risk rule |
| `test_dashboard.py`, `test_recommendation_service.py` | 5 each | Analytics and reports; ranking |
| `test_ingestion.py`, `test_persona_service.py` | 4 each | Pipeline ingest; per-pair failure isolation |
| `test_admin.py` | 3 | Role enforcement |
| `test_sentiment_service.py` | 2 | Classification |
| `test_e2e_pipeline.py` | 1 | Full journey (mocked externals) |

**A limitation worth stating plainly:** every automated test mocks the GAN, the image API and the LLM. That is deliberate — real calls would make CI slow, costly and non-deterministic — and it is exactly why §8.3's bug survived 67 passing tests. Mocked tests prove orchestration; the evaluation scripts in `backend/scripts/` and real end-to-end runs prove behaviour.

### Real runs

- **Full journey through the real UI** (2026-09, real GAN + real LLM, real browser): register → upload → simulate (2 iterations, 6 variants) → 29 of 30 genuine persona reactions → recommendation → PDF and CSV export.
- **Hybrid pipeline end to end through the API** (2026-10-13): Skechers sneaker, 2 variants, 1 round, 135 s; both variants rendered by Cloudflare and upscaled by the ESRGAN, 5 personas each reacting to the image, recommendation and reports generated.

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

First-time setup: `python -m venv .venv`, `pip install -r requirements.txt`, copy each `.env.example` to `.env`, `alembic upgrade head`, `python -m scripts.seed_personas`, `npm install`.

**The full pipeline** needs, in `backend/.env` (see `backend/.env.example`):

| Setting | Value | Needs |
|---|---|---|
| `GENERATOR_BACKEND` | `hybrid` | `IMAGE_PROVIDER=cloudflare`, `IMAGE_API_KEY` (Cloudflare API token with Workers AI permission), `CLOUDFLARE_ACCOUNT_ID` |
| `DIFFUSION_OUTPUT_SIZE` / `SR_ENABLED` | `512` / `true` | the trained ESRGAN weights at `SR_CHECKPOINT` |
| `OLLAMA_MODEL` / `LLM_VISION` | `gemma4:31b-cloud` / `true` | Ollama installed and signed in (`ollama signin`) |
| `REVIEW_GROUNDING_ENABLED` | `true` | the review index: `python -m scripts.build_review_index` (~3 min on GPU) |

With none of these set, the system runs the GAN-only pipeline with local Ollama. Admin access is operational-only — promote an account via `auth_service.promote_to_admin()`.

---

## 12. Current state and what remains

**Working:** authentication, product upload, scenario configuration, hybrid variant generation (diffusion render + trained ESRGAN upscaler, FastGAN fallback), persona simulation with images and real-review grounding, sentiment, risk detection, the optimisation loop, recommendations, the business-facing dashboard, PDF and CSV reports, and the full React UI. 730,713 real reference rows in Postgres. 160 tests (159 pass, 1 skipped).

**Not done:**
- **Cloud deployment and production verification (Steps 42–43).** `render.yaml` and a runbook exist, but no live deploy has been performed, and the hybrid pipeline adds requirements: hosting the FastGAN and ESRGAN weights, a hosted persona model, the review index, and the two API keys — see `docs/deployment.md`.
- **Frontend UI/UX overhaul** — planned next; the results page was rewritten (§6.8), the other pages are unchanged.
- **Guide sign-off** on hosted pretrained models against the public-data constraint (PRD §5.6).
- **Remaining Phase 17 options** — Celery+Redis queue, dynamic LLM-authored personas, MLflow tracking. None are required for certified scope.

**Known limitations, stated rather than hidden:**
- Variants differ mainly in **colourway**; the diffusion model preserves the product's design rather than inventing new ones.
- The FastGAN alone is not photorealistic (FID 274.0), and its candidates do not steer the diffusion render (§8.4).
- Cloudflare's safety filter refuses some ordinary product photos; after three re-seeded attempts the variant falls back to the GAN image.
- The free tiers have limits: Cloudflare's daily allowance (~270 renders at 512 px) and Ollama Cloud's usage allowance (one request at a time).
- Persona reactions are simulated; the business thresholds ("likely to buy" ≥ 60%, interest levels at 40/60%) are presentation choices, not calibrated against sales. Reports say so.
- Persona-response consistency is measured on a sample, not every pair.
- Trained weights exist only on the development machine (excluded from version control).
- Product photos and prompts are sent to Cloudflare and Ollama Cloud when the hybrid pipeline and hosted model are on.

---

*Report updated 2026-10-13.*
