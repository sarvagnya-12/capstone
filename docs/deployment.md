# Deployment Runbook (Step 42) — Render

Target: [Render](https://render.com), deployed from `render.yaml` (a "Blueprint")
at the repo root. This is a from-scratch, copy-pasteable runbook — follow it in
order the first time you deploy.

## Why Render

Chosen over a raw AWS/Azure/GCP setup for this project's scale: one Blueprint
deploys all three pieces (backend, static frontend, managed Postgres) with
minimal manual infrastructure work, has a real free tier, and needs no
separate load balancer/networking setup for a demo-scale deployment. See
`IMPLEMENTATION.md`'s Step 42 notes for the reasoning behind the specific
service types chosen (Docker backend + **static site** frontend, not a second
Docker+nginx service) — in short, Render's internal service-to-service
hostnames aren't predictable before first deploy, so the frontend calls the
backend's public URL directly (CORS-enabled) instead of relying on a
same-origin reverse proxy the way local `docker compose up` does.

## Before deploying the current pipeline (required, as of 2026-10-13)

This runbook was written for the MVP. The pipeline has changed since (see
`REPORT.md` §8.4–8.6), and **a deployment from the current code will not
generate images until the first item below is fixed** — even with the
GAN-only default. None of these have been done or tested in a real deploy.

1. **Model weights.** `backend/entrypoint.sh` still downloads the superseded
   StyleGAN2 cat checkpoint (`afhqcat.pkl`), but the app now defaults to the
   FastGAN at `storage/fastgan/models/shoes150k/model_20.pt`. The weights
   exist only on the development machine (excluded from git) and must be
   hosted somewhere the server can download them, with `entrypoint.sh`
   updated to fetch them:

   | File | Size | Needed for |
   |---|---|---|
   | `fastgan/models/shoes150k/model_20.pt` + `.config.json` | 221 MB | Any image generation (GAN path, and the hybrid fallback) |
   | `esrgan/models/shoes512/net_g_ema_050000.pt` | 47 MB | `SR_ENABLED=true` |
   | `review_index/` (3 files) | 279 MB | `REVIEW_GROUNDING_ENABLED=true` — or rebuild on the server with `python -m scripts.build_review_index` (needs the `ref_reviews` table populated) |

2. **Persona model.** A deployed server cannot reach a local Ollama. Either
   set `LLM_PROVIDER=anthropic` with `ANTHROPIC_API_KEY` (paid), or use Ollama
   Cloud directly: `OLLAMA_BASE_URL=https://ollama.com`,
   `OLLAMA_API_KEY=<key from ollama.com/settings/keys>`,
   `OLLAMA_MODEL=gemma4:31b`. The direct Ollama Cloud route has **not** been
   tested from this code (development used a local Ollama signed in to the
   cloud) — try it with the one-line check in `REPORT.md` §11 first.

3. **Hybrid pipeline settings** (set in the Render dashboard as secrets, never
   in `render.yaml`): `GENERATOR_BACKEND=hybrid`, `IMAGE_PROVIDER=cloudflare`,
   `IMAGE_API_KEY` (Cloudflare API token with the Workers AI permission),
   `CLOUDFLARE_ACCOUNT_ID`, `DIFFUSION_INIT=product`, `DIFFUSION_OUTPUT_SIZE=512`,
   `SR_ENABLED=true`, `LLM_VISION=true`, `REVIEW_GROUNDING_ENABLED=true`. Each is
   documented in `backend/.env.example`. Without them the deployment runs the
   GAN-only pipeline.

4. **Memory.** PyTorch, the FastGAN, the ESRGAN and the sentence-embedding
   model are all loaded by the backend; Render's free instance size is very
   likely too small for this. Check current instance limits and expect to need
   a paid instance — not measured.

5. **Secrets.** `render.yaml` generates `JWT_SECRET_KEY` on Render. If you
   deploy anywhere else, replace the `changeme-…` placeholder from
   `backend/.env.example`.

## Prerequisites

- A Render account (free to create).
- This repository pushed to GitHub, with Render given access to it (Render's
  own GitHub App install flow, prompted the first time you connect a repo).
- Nothing else — `render.yaml` and both Dockerfiles are already in the repo.

## Step 1 — Deploy the Blueprint

1. In the Render dashboard: **New +** → **Blueprint**.
2. Select this repository. Render detects `render.yaml` automatically and
   shows a preview of the 3 resources it will create: `dryrunai-db`
   (Postgres), `dryrunai-backend` (Docker web service), `dryrunai-frontend`
   (static site).
3. Click **Apply**. Render provisions the database first, then builds and
   deploys both services. The backend build includes a real `pip install`
   of `torch`/`transformers`/etc. and can take several minutes the first
   time — this is expected, not stuck.
4. Wait for both services to show a green **Live** status before continuing.

At this point the two services almost certainly **cannot talk to each
other correctly yet** — that's expected, not a failure. `render.yaml` ships
with placeholder URLs for exactly the two values that can only be known
*after* first deploy. Step 2 fixes this.

## Step 2 — Wire up the two services' real URLs (required)

1. Open each service's page in the Render dashboard and copy its real URL
   (shown at the top, format `https://<something>.onrender.com`) — one for
   `dryrunai-backend`, one for `dryrunai-frontend`.
2. On **dryrunai-backend** → **Environment**: set `CORS_ORIGINS` to the
   frontend's real URL (exactly as copied, no trailing slash). Save —
   Render restarts the service automatically to pick this up.
3. On **dryrunai-frontend** → **Environment**: set `VITE_API_BASE_URL` to
   the backend's real URL (no trailing slash). Save, then go to **Manual
   Deploy** → **Deploy latest commit** and trigger it explicitly — a static
   site bakes this value in at *build* time, so saving the env var alone
   does not rebuild the site.
4. Wait for the frontend's redeploy to finish.

## Step 3 — Verify

Open the frontend's URL in a browser and run through the real user journey:
register → log in → upload a product → configure a scenario → run a
simulation → watch it complete → view the dashboard → download a report.
Model weights download on the backend's first start (`entrypoint.sh`) — the
first simulation run will be slower than subsequent ones for this reason alone,
not a bug. (`entrypoint.sh` must be updated first; see "Before deploying the
current pipeline" above.)

If the frontend can't reach the backend (network errors in the browser
console), double check Step 2 was applied to *both* services and that the
frontend redeploy in Step 2.3 actually completed.

## Persona reactions need a reachable model

Without a reachable persona model, reactions are clearly-marked `[LLM_ERROR]`
placeholder text — the rest of the pipeline still runs around it, but the
results are meaningless. `render.yaml` defaults to `LLM_PROVIDER=anthropic`:
set `ANTHROPIC_API_KEY` under **dryrunai-backend** → **Environment** (a key from
[console.anthropic.com](https://console.anthropic.com/); `sync: false`, so it
only ever exists in the dashboard), or switch to Ollama Cloud as described in
"Before deploying the current pipeline" above.

## Notes on the free tier

- The backend's `disk` (for the GAN checkpoint + uploaded images to persist
  across restarts) requires a **paid** Render plan — free web services don't
  support attached disks. On the free plan, the checkpoint just re-downloads
  on every restart (slow, not broken); uploaded product/variant images are
  lost on restart too. Upgrade `dryrunai-backend`'s plan in `render.yaml` (or
  directly in the dashboard) if this matters for your presentation.
- Free web services on Render spin down after a period of inactivity and take
  a noticeably slower "cold start" on the next request. If you're presenting
  live and want to avoid that delay, load the frontend URL a few minutes
  before you present, or upgrade to a paid plan beforehand.
- Render's free Postgres plan may have its own time/row limits — check
  [render.com/pricing](https://render.com/pricing) for current terms before
  relying on it past a short-term demo.

## What Step 43 covers (not this document)

This runbook confirms the deployment *works*. Step 43 (Production
Verification) is the separate pass confirming the NFRs it's supposed to
satisfy — HTTPS enforcement, a real (non-mocked) end-to-end run, database
backups — recorded in `docs/production_verification.md`.
