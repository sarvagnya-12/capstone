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
The GAN checkpoint (~364MB) downloads automatically on the backend's first
request that needs it (`entrypoint.sh`, Step 42) — the first simulation run
will be slower than subsequent ones for this reason alone, not a bug.

If the frontend can't reach the backend (network errors in the browser
console), double check Step 2 was applied to *both* services and that the
frontend redeploy in Step 2.3 actually completed.

## Optional — enable real LLM-driven persona reactions

Without this, persona reactions are clearly-marked `[LLM_ERROR]` placeholder
text (Steps 20-21's disclosed, documented gap) — the rest of the pipeline
still runs correctly around it. To enable real reactions: **dryrunai-backend**
→ **Environment** → set `ANTHROPIC_API_KEY` to a real key from
[console.anthropic.com](https://console.anthropic.com/). This field is
`sync: false` in `render.yaml`, meaning Render never reads it from the repo —
it only ever exists as a value you set directly in the dashboard.

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
