# Training DryRunAI's GAN on Another Machine

How to move this project to a faster GPU box, run the large training cycle, and
bring the result back. Training needs **no database, no frontend, and no
Ollama** — it is a self-contained PyTorch job.

---

## 1. Where things stand

| | |
|---|---|
| Training corpus | **281,589** images, 256×256 RGB, **4.22 GB** |
| Corpus location | `Capstone Dataset (Archived)/Capstone Dataset/DryRunAI/_ingestion_tools/gan_training_images/` |
| Current shipping model | `backend/storage/fastgan/models/shoes150k/model_20.pt` |
| Its score | **FID 274.0** on a 256-image common reference set |
| Its exposure | 50,000 steps × batch 8 = 400k samples over 150,031 images = **2.67 epochs** |

The corpus was just doubled from 150,031 to 281,589 (300,000 metadata records →
293,670 had a `hi_res` URL → 12,081 failed download or the aspect/size filters).
All 281,589 were verified to decode as valid 256×256 RGB with zero corrupt files.

### What the extra data does and does not fix

Measured on 1,200-image samples from each half of the corpus:

| Half | mean saturation | low-sat (<0.15) | vivid (>0.45) |
|---|---|---|---|
| Original 150,031 | 0.231 | 41.4 % | 13.2 % |
| New 131,558 | 0.224 | 41.2 % | 11.8 % |

The new half is **colour-identical** to the old one. So the extra data does
**not** fix the known failure mode (bright colourways generate worst; the
discriminator had learned "dark = real" at r = −0.888). That still needs the
colour-rebalancing work, which is separate.

What the extra data *does* fix is the epoch arithmetic — but only if step count
rises with it. At the old 50,000 steps × batch 8, 281,589 images would be just
**1.42 epochs**, which is worse than what we already have. **More data is only
worth having here because the faster GPU can afford far more steps.** That is
the whole reason this run makes sense.

---

## 2. What to copy

Three things. Two of them are gitignored, so **`git clone` alone is not enough.**

| What | Size | How |
|---|---|---|
| The repo | ~50 MB | `git clone` (or copy the folder) |
| The image corpus | 4.22 GB | Manual copy — gitignored |
| `shoes150k/model_20.pt` + `.config.json` | 211 MB | Manual copy — gitignored |

Copy the baseline checkpoint even though you are training from scratch. You need
it on the new machine to **re-score the baseline alongside the new model** (see
§7 — this is not optional for a valid comparison).

Do **not** bother copying: `backend/storage/products/`, the other 20 `shoes150k`
checkpoints, the `shoes/` run, `.venv/`, `node_modules/`.

A 4.4 GB transfer over USB 3 is a few minutes; over a network, use
`robocopy /E /MT:16` or `rsync -a --info=progress2`.

---

## 3. Prerequisites on the new machine

- **NVIDIA GPU with ≥12 GB VRAM** and a driver supporting CUDA 12.6
- **Python 3.11** (3.11.9 is what this project is built against)
- ~40 GB free disk for checkpoints and sample grids
- Verify the GPU first: `nvidia-smi`

Linux is fine and slightly faster for dataloading. The commands below are shown
for both.

---

## 4. Setup

```bash
git clone <your-repo-url> dryrunai && cd dryrunai/backend
python -m venv .venv
```

Activate it:

| Shell | Command |
|---|---|
| PowerShell | `.\.venv\Scripts\Activate.ps1` |
| cmd | `.venv\Scripts\activate.bat` |
| bash / Linux | `source .venv/bin/activate` |

Install — **CUDA wheels first**, because `requirements.txt` pins `+cu126` builds
that are not on PyPI:

```bash
pip install torch==2.13.0+cu126 torchvision==0.28.0+cu126 --index-url https://download.pytorch.org/whl/cu126
pip install -r requirements.txt
```

Create a `.env`. **Training does not need one, but the evaluation script does** —
it imports `app.core.config` transitively via `app.services.image_preprocessing`,
and that requires `DATABASE_URL` and `JWT_SECRET_KEY` or it raises a pydantic
`ValidationError`. Nothing ever connects to the database on a training box, so
the example values are fine as-is:

```bash
cp .env.example .env
```

Now place the copied files:

```
backend/storage/fastgan/models/shoes150k/model_20.pt
backend/storage/fastgan/models/shoes150k/.config.json     <- required, not optional
<anywhere>/gan_training_images/                            <- the 281,589 images
```

`.config.json` records `image_size` and `attn_res_layers`; `load_fastgan_generator()`
refuses to load a checkpoint without it, by design.

### Verify before committing hours

```bash
python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
python scripts/compare_checkpoints.py --images-dir "<path>/gan_training_images" --count 64 storage/fastgan/models/shoes150k/model_20.pt
```

The second command proves the whole stack works end to end: CUDA, the corpus
path, checkpoint loading, and FID. If it prints a number, you are ready.

---

## 5. Pick the configuration

Start from your VRAM tier, then raise `--batch-size` until `nvidia-smi` shows
~80 % utilisation. All rows assume 256 px and `--amp`.

| VRAM | `--batch-size` | `--num-workers` |
|---|---|---|
| 12 GB | 16 | 8 |
| 16 GB | 24 | 8 |
| 24 GB (4090 / 3090) | 32 | 12 |
| 40 GB (A100) | 64 | 16 |
| 80 GB (A100/H100) | 64 (see note) | 16 |

**Do not simply trade steps for batch size.** GAN quality tracks the *number of
discriminator updates*, not only total samples, and FastGAN-class models
generally want ≥100,000 iterations. Batch 256 for 20,000 steps is not equivalent
to batch 32 for 160,000 steps — it is worse. Past 64, spend the extra VRAM on
`--attn-res-layers 32,64` rather than on a bigger batch.

If you are VRAM-limited but want a larger effective batch, use
`--gradient-accumulate-every N`: it sums gradients over N passes before
stepping, so batch 16 × accum 4 has the gradient quality of batch 64 at the
memory cost of 16 (but takes ~4× as long per step).

**Keep `--lr 2e-4`.** It is FastGAN's own default and tuned for small batches.
Do not linearly scale it to the batch size — an earlier run in this project went
non-finite at step 154 from too high a learning rate. Batch 64 tolerates up to
~3e-4 if you want to push it; the script's NaN guard aborts immediately rather
than burning hours computing nothing, so a blowup costs minutes.

### Target exposure

Aim for **15–20 epochs**, versus the current model's 2.67.

```
epochs = steps × batch_size × accum / 281,589
```

The script prints this on startup, so a misconfigured run is obvious in second
one rather than hour thirty.

| batch | steps | epochs |
|---|---|---|
| 16 | 150,000 | 8.5 |
| 32 | 150,000 | **17.1** ← recommended |
| 64 | 100,000 | 22.7 |

---

## 6. Launch

Recommended run, for a 24 GB card:

```bash
cd backend
python -m app.ml.gan.train_fastgan \
  --images-dir "<path>/gan_training_images" \
  --run-name shoes300k \
  --steps 150000 \
  --batch-size 32 \
  --num-workers 12 \
  --lr 2e-4 \
  --amp \
  --attn-res-layers 32 \
  --aug-prob 0.5 \
  --save-every 5000 \
  --fid-every 10000 \
  --fid-images 1024 \
  --fresh
```

On Windows PowerShell, use a backtick `` ` `` instead of `\` for line
continuation, or put it all on one line.

**Calibrate before walking away.** Let it reach step 500, then read the
`s/step` figure (§7) and multiply by 150,000:

| s/step | 150,000 steps |
|---|---|
| 0.30 | 12.5 h |
| 0.20 | 8.3 h |
| 0.15 | 6.3 h |

For reference, the 6 GB RTX 4050 managed 0.38 s/step at batch 8. If your s/step
is not *much* better than that at a 4× larger batch, dataloading is the
bottleneck, not the GPU — raise `--num-workers`.

### About `--attn-res-layers 32`

This adds a self-attention block to the generator. Every run so far used none,
giving a purely convolutional generator whose receptive field is local — a
plausible cause of output with shoe-like *texture* but not shoe-like *global
shape*. The package's author recommends `32` as the usual first addition.

I verified it works mechanically: it trains, `.config.json` records
`"attn_res_layers": [32]`, the checkpoint round-trips through `Trainer.load()`,
and the app's adapter loads it and generates in-range 256 px output with exactly
one `LinearAttention` module present. **I have not verified it improves
quality** — that is what this run measures.

It changes the architecture, so such a checkpoint **cannot** `--resume` into a
run without it, or vice versa. If you would rather keep the run strictly
comparable to the existing baseline, drop the flag.

### Why a fresh run, not `--resume` from `shoes150k`

`--resume` would save ~5 hours of a ~9 hour run, but it would mean one run with
two different datasets, two batch sizes, and (with attention) two architectures
— unreportable, and impossible to attribute an improvement to. It is also
architecturally incompatible once `--attn-res-layers` is on. The baseline stays
on disk as the fallback, so nothing is lost.

---

## 7. Monitor

In a second terminal:

```bash
cd backend
python scripts/watch_training.py --log <path-to-your-log>
```

Redirect the training output to a log to use this:
`... --fresh 2>&1 | tee storage/fastgan_300k.log` (bash), or
`... --fresh *>&1 | Tee-Object storage/fastgan_300k.log` (PowerShell).

It shows a live progress bar, `d_loss`/`g_loss`, measured **s/step**, and an
ETA. Note that FID will show `(none yet)` — the watcher looks for a `[eval]`
line format that the StyleGAN2 path emitted and this one does not. Read FID from
`storage/fastgan/results/shoes300k/fid_scores.txt` instead.

**Health checks while it runs:**

- `d_loss` and `g_loss` should stay in roughly ±3 and neither should collapse to
  ~0. `d_loss` near 0.000x means the discriminator has won and the generator has
  stopped learning — that killed an earlier attempt in this project.
- Non-finite loss aborts the run automatically; already-written checkpoints stay
  usable.
- Look at the sample grids in `storage/fastgan/results/shoes300k/` with your own
  eyes every few hours. FID missed this project's colour failure entirely.

---

## 8. Evaluate and promote

**Always re-score the baseline in the same command as the candidate.** Do not
compare against the 274.0 figure in this document. That number was computed by
sampling seed 1234 from a *150,031-file* folder; the same seed on the now
281,589-file folder selects **different reference images**, so the scales are
not the same. Scoring both models in one invocation is the only valid
comparison, and the script is built to do exactly that:

```bash
cd backend
python scripts/compare_checkpoints.py \
  --images-dir "<path>/gan_training_images" \
  --count 256 \
  storage/fastgan/models/shoes150k/model_20.pt \
  storage/fastgan/models/shoes300k/model_20.pt \
  storage/fastgan/models/shoes300k/model_25.pt \
  storage/fastgan/models/shoes300k/model_29.pt
```

Use `--count 256`, not less — FID is biased upward at small sample sizes (the
same two checkpoints score 288.6/355.8 at count 64 versus 274.0/313.8 at 256).

**Decision rule, set now rather than after seeing the numbers:**

1. The new checkpoint must **beat the baseline on the same reference set**, in
   the same invocation. If it does not, the baseline stays and the run is
   reported as a negative result.
2. Look at its sample grid before promoting. A better FID with visibly worse
   output is not an improvement.
3. Check the colour tail specifically — are vivid samples still
   disproportionately malformed? That decides whether the colour-rebalance work
   is still needed.

Note that `shoes150k` peaked at its *final* step while the earlier `shoes` run
peaked at step 14,000 and then degraded. Do not assume the last checkpoint is
best — score several.

To promote, edit `GAN_CHECKPOINT` in `backend/app/core/config.py` and update the
comment block recording the comparison, keeping the previous entries so the
history stays readable.

---

## 9. Bring the result back

Copy back only:

```
backend/storage/fastgan/models/shoes300k/<winning>.pt     (~211 MB)
backend/storage/fastgan/models/shoes300k/.config.json     (required)
backend/storage/fastgan/results/shoes300k/fid_scores.txt
a few sample grids, for the report
```

Then on your machine:

```bash
cd backend
python scripts/compare_checkpoints.py --images-dir "<path>/gan_training_images" --count 256 \
  storage/fastgan/models/shoes150k/model_20.pt storage/fastgan/models/shoes300k/<winning>.pt
python -m pytest -q          # expect 78 passed
```

Re-running the comparison locally confirms the file survived the copy and the
checkpoint loads here too. Then update `GAN_CHECKPOINT`, run the app, and
generate variants through the real UI before calling it done.

---

## 10. Quick reference

```bash
# train
python -m app.ml.gan.train_fastgan --images-dir "<corpus>" --run-name shoes300k \
  --steps 150000 --batch-size 32 --num-workers 12 --amp --attn-res-layers 32 \
  --save-every 5000 --fid-every 10000 --fid-images 1024 --fresh

# watch
python scripts/watch_training.py --log storage/fastgan_300k.log

# compare (always include the baseline)
python scripts/compare_checkpoints.py --images-dir "<corpus>" --count 256 <ckpt> <ckpt> ...

# resume after an interruption (same run name, same architecture flags)
python -m app.ml.gan.train_fastgan --images-dir "<corpus>" --run-name shoes300k \
  --steps 150000 --batch-size 32 --num-workers 12 --amp --attn-res-layers 32 --resume
```
