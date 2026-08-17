FROM python:3.11-slim

WORKDIR /app

# System deps: libpq for psycopg, libgl/libglib for Pillow's image codecs.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# requirements.txt pins torch/torchvision to this dev machine's CUDA build
# (+cu126, per its own comment) -- those exact artifacts don't exist on
# PyPI and a plain `pip install -r requirements.txt` would fail on them.
# A demo-scale cloud deployment (Step 42's own framing) isn't expected to
# have a GPU anyway, and app/ml/gan/model.py already falls back to CPU
# automatically when CUDA isn't available (same code path already proven
# on this dev machine, which has no CUDA compiler toolchain either).
#
# PyPI's own default Linux wheel for plain `torch==2.13.0` turned out to
# still bundle ~1.5GB of unused NVIDIA CUDA runtime libraries (confirmed by
# actually building this image and reading the install log, not assumed) --
# so this pulls from PyTorch's dedicated CPU-only index instead, which is
# both correct for this container (no GPU will ever be present) and
# meaningfully smaller to build and pull in Step 42's deployment.
#
# Order matters here: torch/torchvision must install FIRST. transformers/
# torchmetrics/torch-fidelity all transitively depend on torch too, and
# installing requirements.txt as a whole first (as an earlier version of
# this Dockerfile did) let pip satisfy that transitive dependency from the
# default index before the explicit CPU-index install ran -- pip then saw
# "torch==2.13.0 already satisfied" and never actually swapped it, silently
# keeping the CUDA build anyway. Confirmed by rebuilding and reading the
# install log a second time, not assumed to be fixed.
RUN pip install --no-cache-dir torch==2.13.0 torchvision==0.28.0 \
        --index-url https://download.pytorch.org/whl/cpu \
    && grep -v "cu126" requirements.txt > requirements.docker.txt \
    && pip install --no-cache-dir -r requirements.docker.txt

COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
