# Generator Alternatives — GAN, Diffusion, or Both

**Status:** decision document. **No code has been changed.** Nothing here is implemented.

**Why this document exists.** `IMPLEMENTATION.md` Decision #5 resolved the MVP to a GAN and closed the question with a specific escape clause:

> "Stable Diffusion inclusion is not part of this plan at any phase; if desired later, it is a distinct decision requiring separate approval, not something this document schedules."

This is that separate-approval artefact. It does not re-decide Decision #5 — it presents the case for amending it, so the amendment is recorded rather than drifted into.

**The governance constraint this operates under.** `PROJECT_CONTEXT.md:115`, under *"Things that MUST NOT be changed without explicit approval"*:

> "The "GAN-centric" framing/title of the project (per the certified report) — do not silently pivot the core narrative to "diffusion-centric" even though Stable Diffusion appears in the working architecture; that tension is an open decision, not a mandate to switch."

Diffusion is therefore already inside the documented design space — `PRD.md:129` lists the generation module as "StyleGAN/Stable Diffusion", `PRD.md:162` marks Stable Diffusion `[DOCUMENTED DESIGN]` in Phase 3, and `PRD.md:327` logs the tension as **Open Decision #2, priority HIGH**. Adding diffusion closes an open decision. *Removing* the GAN breaks a MUST-NOT.

**Tie-break rule used throughout:** where options are close, the one that most improves the images a viewer actually sees wins, accepting schedule risk. That was set deliberately before the analysis, not chosen to fit the conclusion.

---

## TL;DR

| | Option A — GAN only | **Option B — both (recommended)** | Option C — replace with diffusion |
|---|---|---|---|
| Image quality | Hard ceiling, far from photoreal | **Step change** | Step change (identical to B) |
| Variants derive from the uploaded photo | No, and unfixable by training | **Yes** | Yes |
| Training required | ~9 h on a ≥12 GB GPU | **None — inference only** | None |
| New dependencies | 0 | 3 (`diffusers`, `accelerate`, `safetensors`) | 3 |
| DB migration | — | **None** | None |
| Breaks `PROJECT_CONTEXT.md:115` | No | **No** | **Yes** |
| Keeps a measurable baseline | n/a | **Yes** | No |
| Fits the 6 GB dev card alongside Ollama | Yes | Awkwardly — see §7.1 | Awkwardly |

**Recommendation: Option B.** The decisive point is that **B and C produce identical images**, because they run the same model. C differs only in what it *destroys*. So on a quality criterion there is no argument for replacement — only a "one less code path" maintenance argument, and the maintenance surface turns out to be a single function (§6.1).

---

## 1. What is actually wrong today

Two separate failures. They are usually discussed as one, and only the first is about image quality.

### 1.1 Output quality (measured)

`app/core/config.py:44-53` records the comparison that selected the shipping checkpoint, all scored against one common 256-image reference set:

| Checkpoint | Corpus | Step | FID |
|---|---|---|---|
| `shoes/model_28.pt` | 25k | 14,000 | 313.8 |
| `shoes150k/model_18.pt` | 150k | 45,000 | 278.2 |
| **`shoes150k/model_20.pt`** | 150k | 50,000 | **274.0** |

FID is lower-is-better. `REPORT.md:262` assesses this honestly:

> "output is recognisably footwear with laces, soles and realistic colourways, but roughly 20% of samples are malformed and none would pass for a product photo. Mature StyleGAN2 on a clean dataset scores FID in the single digits; we are at 288."

*(That 288 is on a different reference scale from the 274.0 above — the two numbers are not comparable, and neither is comparable to the "single digits" figure, which is measured against a large clean dataset. The qualitative conclusion holds regardless: we are an order of magnitude away from photoreal.)*

There is an unexhausted improvement route: `TRAINING_TRANSFER.md` has a costed, ready run — 281,589 images, 150,000 steps at batch 32, ~17 epochs versus the current 2.67, ~9 h on a ≥12 GB GPU. **Its benefit is unmeasured.** It should help; it will not reach photoreal.

### 1.2 Variants have no relationship to the uploaded product

This is the bigger problem and it is invisible in any FID number.

`app/services/gan_service.py:50`:

```python
results = generate_variants(str(product.id), n, attribute_hints=attribute_hints)
```

Only the product **ID** is passed. In `app/ml/gan/inference.py:105`, that ID is hashed to a seed and used to draw a random latent:

```python
z_anchor = torch.from_numpy(np.random.RandomState(base_seed).randn(1, generator.z_dim).astype("float32"))
```

The uploaded photo is read in exactly one place — `gan_service.py:76-79` — and only as the real-image reference for FID. It never reaches the generator.

**Consequence:** the variants shown to the user, judged by the personas, scored by the optimiser, and rolled into the PMF number are random draws from the footwear distribution. They are not variants *of the uploaded product*. A user uploading a white running shoe can receive four unrelated dark boots.

`inference.py:24-32` explains why image conditioning was skipped, and the reason has since expired:

> "Base-image-conditioned GAN inversion … is deliberately NOT implemented: this checkpoint's domain (AFHQ cats) is unrelated to uploaded product photos"

That docstring is stale — Step 17 replaced the cat checkpoint with a footwear model trained on 281,589 shoe photos. The stated blocker is gone. Inversion is now *possible* on the GAN path, but it costs hundreds of optimiser steps per request and still only finds the nearest point the GAN can already express — which, at FID 274, is not much. Diffusion img2img solves the same problem in one forward pass and with a far better decoder.

---

## 2. Option A — keep the GAN only

**Pros**
- Zero new dependencies, zero new failure modes, zero licensing questions.
- "GAN-centric" title and Decision #5 untouched; no approval needed from anyone.
- The improvement path is already built and costed (`TRAINING_TRANSFER.md`), including the fair-comparison harness (`backend/scripts/compare_checkpoints.py`).
- Cheap inference (~50 ms/image, estimated) and a working CPU fallback, so Step 42 deployment stays viable on a GPU-less instance — `Dockerfile:14-18` notes "A demo-scale cloud deployment … isn't expected to have a GPU anyway".
- The three documented StyleGAN2 failures plus the from-scratch FastGAN result are genuine, defensible engineering content.

**Cons**
- **Hard quality ceiling.** FastGAN from scratch on a consumer GPU will not approach photoreal. The honest expected outcome of the 150k-step run is "noticeably better, still obviously synthetic".
- **§1.2 is unfixed.** More training does not make variants resemble the uploaded product. This is a correctness problem in the product's core claim, not a polish issue.
- Colour control stays a post-processing hack (`_apply_hue_shift`, `inference.py:66-73`) applied to the whole image, including background — not a real design variation.
- The known colour bias remains: the corpus is ~41% low-saturation against ~12% vivid (measured this session on 1,200-image samples per half), and the discriminator had learned "dark = real" at r = −0.888.

**Verdict:** the safe option, and the only one that fails the stated tie-break rule outright.

---

## 3. Option B — keep the GAN, add a diffusion backend (recommended)

Add `app/ml/diffusion/` as a second generator behind a config switch. The GAN stays selectable and stays the measured baseline.

**Concrete shape:** Stable Diffusion 1.5 **img2img**, conditioned on the 256×256 preprocessed upload that `image_preprocessing.preprocess_image()` already produces, at denoise strength ~0.4–0.6 so product identity survives while styling changes. Prompt built from the product's own name/description/category plus the colour term the optimiser asks for. **Inference-only — no training at all.**

**Pros**
- **Step change in image quality.** SD 1.5 renders photorealistic footwear out of the box. *(Expected, not measured — see §7.6.)*
- **Fixes §1.2 directly.** Variants become genuine restyles of the user's actual product, which is what the PRD's "N design variants" was always meant to be.
- **Colour control becomes real.** A prompt colour term regenerates the product in that colourway instead of hue-rotating the whole bitmap, background included.
- **No training required**, which resolves PRD Open Decision #4 (from-scratch vs fine-tune vs inference-only, CRITICAL) far more comfortably than GAN training ever did against the certified 8 GB / "GPU recommended" hardware spec.
- **Keeps the baseline**, so the project gains a real GAN-vs-diffusion comparison. That also closes PRD Open Decision #5 (no realism metric defined, HIGH) using the harness that already exists.
- **No migration, and a one-function seam** (§6).
- Optional later upgrade path: LoRA fine-tune on the 281,589-image corpus for brand/domain consistency. Not needed for v1.

**Cons**
- Two code paths to maintain, two sets of tests.
- ~3–5 s/image versus ~50 ms (estimated), and VRAM contention with Ollama on the 6 GB card (§7.1).
- Reintroduces pretrained weights, reversing part of Decision #6 (§7.3).
- Needs a GPU in production; the GAN's CPU fallback does not carry over (§7.5).
- Costs time in late September with Steps 42 and 43 still open (§7.7).

---

## 4. Option C — replace the GAN with diffusion

**Pros**
- One generator, one code path, one set of tests. Genuinely simpler to maintain.
- Deletes the latent-space vocabulary that currently leaks into `optimization_service` and `prompt_templates`.
- No dual-backend config surface.

**Cons**
- **No quality benefit over B whatsoever.** Same model, same images. Every gain attributed to C is a gain of B.
- **Breaks `PROJECT_CONTEXT.md:115`**, an explicit MUST-NOT-without-approval item, and contradicts the certified report's title. A project titled *"A GAN-Centric Generative AI Framework"* that ships no GAN invites exactly one question in a viva, and it has no good answer.
- **Discards Step 17 and the three StyleGAN2 failure results** (`IMPLEMENTATION.md:24-28`). Those negative results are real content — arguably the most rigorous work in the project.
- **Destroys the comparison.** With no baseline there is no way to demonstrate the diffusion model is better; "it looks nicer" is not a measurement.
- Loses the CPU deployment fallback with nothing retained behind it.

**Verdict:** strictly dominated by B. The only honest case for C is maintenance cost, and §6.1 shows that cost is one function and one config field.

---

## 5. Other generators considered

All VRAM figures are approximate, for fp16 inference, against the 6 GB RTX 4050.

| Model | VRAM | Verdict |
|---|---|---|
| **SD 1.5** (+ img2img) | ~3.5 GB | **Recommended.** Fits, best img2img/ControlNet/IP-Adapter ecosystem, 512px native. |
| SD-Turbo | ~3.5 GB | Good fallback if latency bites — 1–4 steps, sub-second. Slightly weaker than SD 1.5 at 512px. |
| SDXL-Turbo | ~7 GB | Better quality, needs `enable_model_cpu_offload()` on 6 GB. Viable on the bigger GPU. |
| SDXL base | ~10 GB | Best open quality at 1024px, but slow with offload on 6 GB. Reasonable on the ≥12 GB machine. |
| PixArt-α 512 | ~2.5 GB | Small and surprisingly good, but a thinner img2img ecosystem — more custom work for the §1.2 fix. |
| FLUX.1-schnell | ~12 GB+ | Apache 2.0 (attractive licensing), but 12B parameters. Not viable on 6 GB even quantised. |
| StyleGAN3 / BigGAN | — | Same from-scratch compute problem as FastGAN, and BigGAN is explicitly flagged in `PRD.md:241` as demanding "extremely high computational resources". No advantage. |
| GAN inversion on our own FastGAN | ~1 GB | Fixes §1.2 *only*, and still bounded by a FID-274 decoder. Cheap, but a small win on a weak base. |
| DALL·E 3 / Imagen / Ideogram (hosted) | 0 | Rejected: reintroduces per-call billing, which is precisely what the Anthropic→Ollama switch (`REPORT.md` §8.1) existed to escape. Also sends product data off-machine. |

---

## 6. What Option B actually costs to build

Less than it looks. The seam was partly designed for this.

### 6.1 The integration surface is one function

- **One production import site.** `gan_service.py:9-10` is the *only* place outside `app/ml/gan/` that imports the GAN package. Nothing in `app/api/`, `app/models/`, or `app/schemas/` touches it. `simulation_orchestrator.py:61` calls `gan_service`, not the GAN.
- **No database migration.** `app/models/product_variant.py:34-36` — `generation_method` is a plain `String` and `attributes` is `JSONB`. Both generators coexist in the same table, and `report_service` already selects `generation_method` into CSV/PDF.
- **One test seam.** `tests/conftest.py:276` monkeypatches `app.ml.gan.inference._get_generator`. No test in the suite loads a real checkpoint, so a diffusion backend needs stub modules, not GPU infrastructure.

### 6.2 The optimiser's vocabulary maps 1:1 — the finding that changes the arithmetic

The worry was that the feedback-optimisation loop (a core PRD requirement) speaks latent-space and would need rewriting. It does speak latent-space, but every term has a direct diffusion analogue. `optimization_service.propose_next_attributes` (L102, returning at L118-122) emits exactly three keys:

| Optimiser hint | Diffusion equivalent |
|---|---|
| `anchor_seed` | `torch.Generator` seed — direct |
| `perturbation_radius` | img2img `strength` — direct (both mean "how far from the anchor") |
| `hue_shift_center_degrees` | a prompt colour term via the **existing** `_HUE_NAMES` table (`prompt_templates.py:34-42`) |

And the persona layer was written to expect this. `prompt_templates.py:86-87`:

> "Any genuinely descriptive attributes a future generator adds (color, texture, layout, branding_style — the vocabulary the schema documents)"

**Consequence:** if the diffusion backend populates the same `attributes` key names, then `optimization_service`, `prompt_templates`, `report_service`, the schemas and the DB all keep working **unchanged**. The feedback loop keeps functioning with no translation layer.

One hard requirement: `gan_service.py:67` reads `result.attributes["generation_method"]` with a bare subscript, so a missing key is a `KeyError`, not a default.

### 6.3 New code

- `app/ml/diffusion/provider.py` — the backend, plus `app/ml/diffusion/inference.py` returning the existing `VariantResult(image, attributes)` dataclass.
- `app/core/config.py` — a `GENERATOR_BACKEND: Literal["gan", "diffusion"] = "gan"` field (default keeps current behaviour) plus model/step/strength settings.
- A factory that `gan_service` calls instead of importing `generate_variants` directly.
- `requirements.txt` — `diffusers`, `accelerate`, `safetensors`. `transformers==5.15.0` is **already pinned** (the sentiment stage uses it).
- Tests mirroring `tests/test_llm_provider.py`.

### 6.4 Reuse the pattern that already exists

This project already solved "two interchangeable backends behind a config switch" for LLMs. Copy `app/ml/llm/provider.py` rather than inventing a second style:

- a `Protocol`, not an ABC — structural typing is what lets `conftest.FakeLLMProvider` drop in without touching the module
- a `get_*_provider()` factory that holds the domain knowledge, keeping the provider classes generic
- one `*ConfigurationError` carrying an actionable message (it names the address *and* the fix)
- lazy SDK import inside `__init__`, so an unused backend's dependency need not be installed
- a `Literal[...]` config field, giving pydantic startup validation

---

## 7. Costs and risks we accept

### 7.1 VRAM contention is real on the dev card

SD 1.5 fp16 (~3.5 GB) plus `llama3.1:8b` (~5 GB) exceeds 6 GB. `simulation_orchestrator._run_pipeline` alternates generation → personas every round, so they would swap repeatedly. `provider.py:65-67` records the cost:

> "the first call after a cold start pays for loading the model into VRAM (measured ~49s for llama3.1:8b on an RTX 4050), versus ~3s once it is resident."

Expect roughly 3 minutes of extra load time over a 3-round simulation. Mitigations, in order of preference: run on the ≥12 GB machine (problem disappears); drop to `llama3.2:3b` (~2 GB, both fit); or explicitly unload between stages with `keep_alive: 0` and `torch.cuda.empty_cache()`. The suite already documents this contention — `tests/test_llm_provider.py:123-132` uses a generous probe timeout specifically because "Ollama shares the same 6GB GPU as the GAN tests".

### 7.2 Latency

~3–5 s/image at 20–30 steps, versus ~50 ms for the GAN (both estimated). Defaults are 3 rounds × 4 variants = **12 images**; the API permits 10 × 20 = **200** (`schemas/simulation.py:42-43`). Generation is synchronous, in-process, on the critical path of a FastAPI `BackgroundTasks` job — Decision #1 ruled out Celery for the MVP. At defaults this adds ~1 minute per simulation against a persona stage already costing ~60 s/round, so it is not the bottleneck. At the 200-variant ceiling it would be.

### 7.3 It reintroduces pretrained weights

Decision #6's revision states "No pretrained weights are used." Using SD reverses that and must be recorded, not glossed.

**Mitigating precedent:** the project already ships pretrained weights. `app/ml/nlp/sentiment.py:20` loads `cardiffnlp/twitter-roberta-base-sentiment-latest` via a `transformers` pipeline. So the principle at stake is narrower than it appears — it applies to the *generator*, and the amendment is to Decision #6's scope, not to a project-wide rule.

### 7.4 Licensing and the public-data constraint

SD 1.5 is CreativeML OpenRAIL-M, which permits research use, and it was trained on LAION — public data. So this is arguably compliant with §5.6. But `PROJECT_CONTEXT.md:117` makes public-data-only a MUST-NOT-change item, so the constraint should be **explicitly extended to cover pretrained weights as a recorded decision**, rather than assumed to be satisfied. Worth a line to the guide. *(Note the existing StyleGAN2 checkpoint is under the NVIDIA Source Code License — non-commercial research only — so the project already carries a restrictive weights licence.)*

### 7.5 Deployment

`Dockerfile:14-18` relies on the GAN's automatic CPU fallback and states a demo deployment "isn't expected to have a GPU anyway". SD on CPU is ~60–90 s/image — not viable. Step 42 would need a GPU instance, or the deployed build would have to stay on the GAN backend via `GENERATOR_BACKEND=gan`. The config switch makes that a one-line environment difference, which is an argument *for* B over C: **C would leave no deployable CPU path at all.**

### 7.6 The quality claim is unmeasured

I expect a large improvement, but I have **not** measured it. Treat it as a hypothesis until scored. And do not score it on FID alone — `TRAINING_TRANSFER.md` records the relevant lesson: FID missed this project's colour-correlated failure entirely. Any comparison must include looking at sample grids.

### 7.7 Timeline

It is late September in a February–October window. Steps 42 (cloud deployment) and 43 (production verification) are open, and every box in `IMPLEMENTATION.md` §10 Definition of Done is still unchecked. The user has accepted this risk, and the `GENERATOR_BACKEND` default of `"gan"` means an unfinished diffusion path cannot break the working demo. Flagged anyway.

---

## 8. Recommendation

**Adopt Option B.** Add a diffusion backend behind `GENERATOR_BACKEND`, defaulting to `"gan"`, conditioned on the uploaded product photo via SD 1.5 img2img. Keep the GAN as the baseline and finish the 300k training run regardless — it is what makes the comparison meaningful.

Three reasons, in order of weight:

1. **It is the quality-maximising choice.** B and C yield identical images, so B is not a compromise between quality and safety — it is the same quality with the baseline retained.
2. **It fixes the §1.2 correctness problem**, which no amount of GAN training addresses, and which undermines the product's central claim more than the pixel quality does.
3. **It costs less than it appears** — one function, one config field, no migration, and an optimiser vocabulary that already maps 1:1 onto diffusion parameters.

Sequencing: build it behind the default-off switch, measure both on a common reference set *and* by eye, then decide what the demo ships with. That decision can be made after the measurement rather than before it.

---

## 9. What would reverse this

Set now, rather than after seeing results:

1. **If SD 1.5 img2img at strength 0.4–0.6 does not beat FID 274.0 on a common 256-image reference set** — scored in the same invocation as the GAN baseline, per `TRAINING_TRANSFER.md` — the diffusion path is reported as a negative result and the GAN stays. Never compare against a number quoted from a document; the reference sample differs.
2. **If VRAM thrashing makes a default 3×4 simulation exceed ~10 minutes** on the target demo machine, fall back to SD-Turbo or `llama3.2:3b` before abandoning the approach.
3. **If Step 42/43 slip because of this work**, stop and ship the GAN. `GENERATOR_BACKEND=gan` makes that a zero-risk revert.
4. **If the guide rules that pretrained generator weights violate §5.6**, Option A is the only remaining choice, and this document becomes the record of why B was considered and declined.

---

## 10. If we proceed — decisions to record

Amendments needed so the change is documented rather than drifted into:

- **`IMPLEMENTATION.md` Decision #5** — amend with a dated revision note in the existing house style (strikethrough the superseded resolution, keep the original rationale as prose, add a `**Scope of the revision:**` clause stating that "GAN-centric" is *preserved* because the GAN remains the default backend and the measured baseline). Decision #6's revision note is the template.
- **`IMPLEMENTATION.md` Decision #6** — narrow "No pretrained weights are used" to the GAN specifically, citing the existing sentiment-model precedent.
- **PRD Open Decision #2** — record as resolved: both, GAN default.
- **PRD Open Decisions #4 and #5** — note that an inference-only diffusion backend and a documented GAN-vs-diffusion FID comparison substantially close these.
- **`REPORT.md`** — add a §8.4 once measured. Its §6.3/§12 figures are already stale (they predate `shoes150k` and the 281,589-image corpus) and should be refreshed in the same pass.
- **Guide sign-off** on the pretrained-weights reading of §5.6 (§7.4) before it is treated as settled.
