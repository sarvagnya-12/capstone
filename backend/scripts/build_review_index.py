"""Build the review-grounding index from ref_reviews (Phase 17 Step 44).

Embeds every usable review (>= 60 characters after HTML clean-up) with a
small sentence-embedding model and writes the index that
app/ml/retrieval/reviews.py searches:

    <out>/embeddings.npy   float16 (N, 384), L2-normalised
    <out>/meta.npz         review_ids, ratings
    <out>/info.json        model, row count, build date

Run once after ingestion (re-run whenever ref_reviews changes):
    cd backend
    python -m scripts.build_review_index            # GPU if free, else CPU
    python -m scripts.build_review_index --limit 2000   # quick trial

~350k reviews take a few minutes on a GPU; on CPU expect much longer. Don't
run it on the GPU while another training job is using it.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.ml.retrieval.reviews import EMBED_CHARS, EMBEDDING_MODEL, MIN_REVIEW_CHARS, clean_review_text  # noqa: E402
from app.models.reference_data import RefReview  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=Path(settings.REVIEW_INDEX_DIR))
    parser.add_argument("--device", default=None, help="cuda / cpu (default: cuda if available)")
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--limit", type=int, default=None, help="Only the first N reviews (for a trial run)")
    args = parser.parse_args()

    import torch
    from sentence_transformers import SentenceTransformer

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")

    print("reading ref_reviews ...", flush=True)
    with SessionLocal() as db:
        query = db.query(RefReview.review_id, RefReview.rating, RefReview.review_text).order_by(RefReview.review_id)
        if args.limit:
            query = query.limit(args.limit)
        rows = query.all()

    ids, ratings, texts = [], [], []
    for review_id, rating, text in rows:
        cleaned = clean_review_text(text)
        if len(cleaned) >= MIN_REVIEW_CHARS:
            ids.append(review_id)
            ratings.append(rating)
            texts.append(cleaned[:EMBED_CHARS])
    print(f"{len(rows):,} reviews read, {len(texts):,} usable (>= {MIN_REVIEW_CHARS} chars)", flush=True)
    if not texts:
        raise SystemExit("no usable reviews -- has ref_reviews been ingested?")

    model = SentenceTransformer(EMBEDDING_MODEL, device=device)
    started = time.time()
    embeddings = model.encode(texts, batch_size=args.batch_size, normalize_embeddings=True,
                              show_progress_bar=True, convert_to_numpy=True)
    print(f"embedded on {device} in {time.time() - started:.0f}s", flush=True)

    args.out.mkdir(parents=True, exist_ok=True)
    np.save(args.out / "embeddings.npy", embeddings.astype(np.float16))
    np.savez(args.out / "meta.npz", review_ids=np.array(ids), ratings=np.array(ratings, dtype=np.float32))
    (args.out / "info.json").write_text(json.dumps({
        "model": EMBEDDING_MODEL, "rows": len(ids), "dim": int(embeddings.shape[1]),
        "min_chars": MIN_REVIEW_CHARS, "built_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2))
    print(f"wrote index of {len(ids):,} reviews to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
