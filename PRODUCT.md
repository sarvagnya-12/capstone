# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

**The person at the keyboard: a capstone evaluator, during a viva.** Confirmed by the user, 2026-10-28. The guide (Dr. Shobha T) and the examining panel drive or watch the interface live while questioning the team. Their job is not to launch a product — it is to judge whether the system genuinely does what the report claims. They arrive knowing the architecture on paper and looking for the gap between the document and the running software.

**The user the product is designed for, in fiction: an organisation/business user.** `PRD.md` §6 (certified, t6.pdf §1.4, Fig 6.5) names a single actor, "User (Business/Organization User)" — a brand, product, or marketing lead at an e-commerce, consumer-goods, fashion, SaaS, retail, agency, or start-up company, deciding which product design to take to manufacture. An `Admin` role also exists (Fig 6.3): manages users, monitors simulations; implemented as a `role` column, not a separate entity.

These two are not in conflict, and both are load-bearing: the screens must hold up as an org user's product *while* making the machinery legible to someone interrogating it. Where the two pull apart, the evaluator wins — that is the real audience.

**No narrative user personas exist and none may be invented.** `PRD.md` §7 states this explicitly and refuses to fabricate them. The segment list above is the full extent of documented audience detail. (Not to be confused with the 20 seeded *simulated customer personas* the system runs internally — a product feature, not an audience.)

## Operating Context

**Usage scene, confirmed: the team's own laptop, driven live.** A 1280–1536px viewport is the real design target; a layout that only resolves on a full-HD desktop does not clear the bar. Not confirmed as required scenes: projector/shared screen, static screenshots in the report PDF, a public Render URL opened cold by strangers. These are undecided rather than excluded — deployment to Render exists (`render.yaml`, `docs/deployment.md`) but was not named as a surface the design must serve.

**The workflow is a 7-stage pipeline** (`REPORT.md` §1, `PRD.md` §13): product upload → scenario configuration → variant generation → persona simulation → sentiment and risk analysis → feedback-driven optimisation → final recommendation. The implemented routes mirror it: Login/Register → ProductUpload → ScenarioConfig → SimulationRun → Dashboard, plus Admin.

**A simulation is long-running and asynchronous.** `POST /api/v1/simulations` returns **202 Accepted** and dispatches a background task; the client polls `GET /simulations/{id}/status`. A measured two-variant, one-round hybrid run took **135 seconds** end to end. Waiting is a core part of the experience, not an edge case — and it is being watched live by someone forming a judgement while nothing appears to happen.

**Parts of the pipeline can degrade or fail at demo time.** The hosted renderer (Cloudflare Workers AI, FLUX.2 Klein 4B) runs on a free daily allowance; when a render fails, the project's own FastGAN output is kept instead, and the reason is recorded in `product_variants.attributes` JSONB alongside `fid_score`. Personas run on `gemma4:31b-cloud` via Ollama Cloud. With default `.env` settings the system runs the reduced GAN-only pipeline on a local Ollama model. Which path produced a given variant is a fact the interface has access to and an evaluator is likely to ask about.

## Product Purpose

Test a product concept — its visual design and its launch scenario (price, target customers, message) — against simulated customers *before* committing to manufacturing. The system generates design variants of an uploaded product photo, shows each variant's image to a vision-capable LLM role-playing a library of predefined customer personas grounded in real reviews, classifies sentiment, flags risk, scores variants, nudges the next round toward better-performing colours, and recommends one variant with the reasoning behind it — in plain business terms, on a dashboard and as a PDF/CSV report.

The problem it addresses (`PRD.md` §2, certified): 70–80% of new products fail within a year, and traditional validation — surveys, focus groups, A/B and beta testing — is slow, costly, small-sample, bias-prone, and mostly happens *after* launch.

**Success for the evaluator audience** is a run they can follow end to end, whose numbers they can trace to something real, and whose limits the system states before they have to ask.

## Positioning

A **decision-support and simulation engine, not a content-generation tool** — confirmed across all three synopsis documents and the certified abstract, and the one claim a neighbouring product could not truthfully copy. The output is a ranked launch decision with its evidence; the generated imagery is an input to that decision, not the deliverable. The project's own framing is that GANs are "a decision-support engine for strategic simulation, not merely an image generator."

The closed loop — generation, LLM behavioural simulation, and feedback-driven optimisation in one pre-launch tool — is the stated research gap (`t6.pdf` §3.8).

**"DryRun"** is the core metaphor: rehearsing a launch before real-world commitment.

## Capabilities and Constraints

**Implemented and working** (`REPORT.md`): JWT auth with user/admin roles · product upload (MIME + extension validation, 10MB cap, auth-gated image serving) · scenario configuration · hybrid variant generation (hosted diffusion render from the product photo → self-trained ESRGAN 2× upscale to 1024px, FastGAN as baseline and fallback) · FID realism scoring · vision-LLM persona reactions grounded in 5 real reviews of similar shoes, one call per persona × variant · sentiment classification (HuggingFace `transformers`) · rule-based risk detection · optimisation scoring with a bounded loop (stop on max iterations **or** PMF plateau) · recommendation with a business-terms summary · PDF/CSV report export · admin user and simulation listing.

**Binding constraints the interface must not violate:**

- **No fabricated numbers or claims.** Confirmed by the user, 2026-10-28. Every metric, score, persona count, and chart value shown must come from a real API response. No placeholder KPIs, invented testimonials, demo-only figures, or illustrative sample data — including in empty and loading states.
- **Be honest about footwear-only scope.** Confirmed by the user, 2026-10-28. The reference corpus is sneakers only (`DRY-SNK-` ID prefix; Zappos/Nike/StockX sources). The interface must not imply the multi-industry framing in the PRD already works end to end.
- **Public data only.** Legal Feasibility, `t6.pdf` §5.6 — no private or proprietary datasets.
- **The GAN-centric framing stays.** `PROJECT_CONTEXT.md` lists this under "must not be changed without explicit approval": the narrative stays GAN-centric and must not be silently re-branded around diffusion, even though a hosted diffusion model does the rendering. Recorded here from repository evidence; not raised as a UI constraint in the 2026-10-28 round.
- **The simulated customers are simulated.** The system "does not guarantee product success but helps organizations reduce uncertainty" (`t6.pdf` Conclusion). Persona reactions must never be presented as real customer research.

**Certified non-functional target relevant to interface work** (`t6.pdf` Table 5.3): Usability — low learning curve, via intuitive UI/UX and **guided workflows**.

**Out of current scope** (`PRD.md` §5, explicitly future work): real-time customer data, multilingual personas, regional consumer modelling, enterprise-scale deployment. Also out of scope: the dataset-extraction pipeline in `Capstone Dataset (Archived)/`, consumed only as an upstream batch source.

**Terminology — use these words, they are the project's own:**

- **Launch scenario** — a bundle of pricing, target-demographic, and messaging parameters a variant is evaluated under.
- **Variant** — one generated synthetic product-design output.
- **Persona simulation** — LLM-generated qualitative feedback, sentiment, and purchase likelihood from a simulated customer profile reacting to a variant.
- **Product–market fit (PMF) score** — an aggregate of persona-level sentiment, engagement, and purchase intent. Not the output of a distinct economic model, and must not be presented as one.
- **Dry run** — testing a launch virtually before real commitment.

**Undecided, not to be invented:** whether academic attribution (BMS College of Engineering, Dept. of ISE, AY 2025-26, team names) must appear in the interface — it was offered in the 2026-10-28 round and not selected, so it is neither required nor forbidden. Whether the deployed Render URL is a surface the design must serve. Several deeper product questions remain open in `PROJECT_CONTEXT.md` ("Open Decisions") — notably the persona diversity/scale mechanism and the depth of "market simulation" — and interface work must not resolve them by implication.

## Evidence on Hand

Real, and unusually strong for a project at this stage — this is what makes the no-fabrication constraint livable:

- **A populated reference corpus in Postgres:** `ref_products` 109,808 rows · `ref_images` 46,272 · `ref_reviews` 496,592 · `ref_market` 36,096 · `ref_product_intelligence` 41,945. Real review text grounds persona reactions; real price ranges ground scenario pricing.
- **20 seeded predefined personas** (`personas` table, via `python -m scripts.seed_personas`).
- **Models the project trained itself:** a FastGAN generator (281,589-image corpus) and an ESRGAN upscaler (RRDBNet + U-Net discriminator), both trained from scratch on an RTX 4050 Laptop GPU (6 GB VRAM) — the VRAM ceiling shaped real decisions, recorded in `REPORT.md` and `GENERATOR_ALT.md`.
- **Measured results, not projections:** FID realism scores per variant; a 135-second two-variant hybrid run; the GAN-vs-diffusion comparison in `GENERATOR_ALT.md` resolved by measurement rather than preference.
- **Working endpoints behind every screen**, including `GET /simulations/{id}/analytics` which already returns a business-terms `insights` payload, and `/report?format=pdf|csv`.
- **Honest absences future work must not paper over:** no real customer validation of the simulated personas against actual purchase behaviour; no human-evaluation protocol for variant realism beyond FID; no benchmark against surveys or focus groups; no users outside the team; no pricing, licensing, or customers. Source documents are in `Capstone Docs/`; no testimonials, press, or case studies exist.

## Product Principles

1. **Credible under questioning.** The audience is looking for the seam between the report and the software. Every number on screen should be traceable to a run, and anything the system does not know should say so before an examiner has to ask.
2. **The decision is the product, not the imagery.** Generated variants are evidence. The deliverable is a ranked recommendation with its reasoning — "take this one forward, because these customer profiles would buy it, and here is what they objected to."
3. **The machinery stays legible.** For most app UI, hiding the pipeline is correct. Here it is the thesis: variant provenance, which generator ran, FID, the personas' actual reasoning, why the loop stopped — all of it is content an evaluator came to see, not plumbing to tuck away.
4. **Honest about its boundaries.** Footwear-only corpus, simulated rather than recruited customers, reduces uncertainty rather than guaranteeing success. Stating limits plainly is a credibility asset in this room, not a weakness.
5. **Waiting is designed, not endured.** A run takes minutes, runs in the background, can partially degrade, and is watched live by someone forming a judgement. Progress, partial results, and honest failure reporting carry real weight.
