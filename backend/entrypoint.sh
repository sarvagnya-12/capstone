#!/bin/sh
set -e

# The GAN checkpoint (Step 15, 364MB) is deliberately not baked into the
# image (Step 41's own design) -- locally it's a bind mount to a file
# that's already on the host. There's no host to bind-mount on a cloud
# deployment (Step 42), so download it once into whatever's mounted at
# /app/storage (a Render Disk or equivalent persistent volume) if it isn't
# there already. Safe to run on every start: idempotent, and a near-instant
# no-op once the file exists.
CHECKPOINT_PATH="/app/storage/models/afhqcat.pkl"
CHECKPOINT_URL="https://nvlabs-fi-cdn.nvidia.com/stylegan2-ada-pytorch/pretrained/afhqcat.pkl"
if [ ! -f "$CHECKPOINT_PATH" ]; then
    echo "GAN checkpoint not found, downloading (~364MB, one-time)..."
    mkdir -p "$(dirname "$CHECKPOINT_PATH")"
    python -c "
import requests
resp = requests.get('$CHECKPOINT_URL', stream=True)
resp.raise_for_status()
with open('$CHECKPOINT_PATH', 'wb') as f:
    for chunk in resp.iter_content(chunk_size=8192):
        f.write(chunk)
"
    echo "Checkpoint downloaded."
fi

echo "Running database migrations..."
alembic upgrade head

echo "Starting API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
