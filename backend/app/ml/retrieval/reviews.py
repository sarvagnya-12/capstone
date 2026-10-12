"""Retrieves real Amazon reviews of similar products to ground persona prompts.

Index (built offline by scripts/build_review_index.py) lives in
settings.REVIEW_INDEX_DIR:
    embeddings.npy  float16 (N, D), L2-normalised sentence embeddings
    meta.npz        review_ids (N,) str, ratings (N,) float32
    info.json       embedding model name, row count, build date

Search is exact (dot product over the whole matrix) rather than approximate:
at ~350k x 384 float16 it is ~270MB and ~0.1s per query, so an ANN library
would add a dependency for no practical gain. Only the k chosen reviews' text
is read back from Postgres (ref_reviews), so the index holds no review text.

Rating balance matters: 64% of the corpus is 5-star, so plain top-k
similarity would ground nearly every persona in praise. Candidates are
therefore drawn from the most similar reviews per rating band (negative /
mixed / positive) instead of the overall top k.
"""

from __future__ import annotations

import html
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
# Reviews shorter than this rarely say anything specific ("Love them!").
MIN_REVIEW_CHARS = 60
# Text embedded per review; long reviews are truncated (MiniLM's own limit is ~256 tokens).
EMBED_CHARS = 600
# Stage 1: this many reviews most relevant to the PRODUCT are kept...
PRODUCT_POOL = 3000
# ...stage 2 re-ranks them by a mix of product relevance and the persona's
# concerns, and the best CANDIDATE_POOL of those are balanced by rating.
CANDIDATE_POOL = 300
# Weight of the persona's concerns in stage 2 (product relevance gets the
# rest). Measured over the 8 seeded lifestyles x 3 products in the dev DB
# (reviews shared per persona pair, of 5 / product relevance of chosen reviews):
#   one combined product+persona query (first version): 3.8 shared, 8 distinct
#   0.30: 3.04 / 0.649    0.50: 2.05 / 0.618    0.70: 1.57 / 0.571
#   0.85: 1.60 / 0.559 -- no further gain past 0.7, only lost relevance.
FOCUS_WEIGHT = 0.7
_SEARCH_CHUNK = 65536
_BEHAVIOR_RE = re.compile(r"Behavior:\s*(.+)", re.IGNORECASE | re.DOTALL)

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


def clean_review_text(text: str) -> str:
    """Amazon review text carries HTML (<br />, entities). Strip it to plain prose."""
    return _SPACE_RE.sub(" ", _TAG_RE.sub(" ", html.unescape(text or ""))).strip()


def rating_band(rating: float) -> str:
    return "negative" if rating <= 2 else "mixed" if rating < 4 else "positive"


def band_quota(k: int) -> dict[str, int]:
    """How many reviews of each band to show: roughly 2 negative, 1 mixed,
    2 positive for k=5 -- deliberately more critical than the corpus itself,
    so personas see what real shoppers complain about, not just praise."""
    negative = max(1, round(k * 0.4)) if k >= 2 else 0
    mixed = 1 if k >= 3 else 0
    return {"negative": negative, "mixed": mixed, "positive": max(k - negative - mixed, 0)}


@dataclass
class ReviewIndex:
    embeddings: np.ndarray  # (N, D) float16, L2-normalised
    review_ids: np.ndarray  # (N,)
    ratings: np.ndarray  # (N,) float32
    model_name: str

    @classmethod
    def load(cls, index_dir: str | Path) -> "ReviewIndex":
        index_dir = Path(index_dir)
        info = json.loads((index_dir / "info.json").read_text())
        meta = np.load(index_dir / "meta.npz", allow_pickle=False)
        embeddings = np.load(index_dir / "embeddings.npy", mmap_mode="r")
        return cls(embeddings=embeddings, review_ids=meta["review_ids"], ratings=meta["ratings"],
                   model_name=info["model"])

    def _similarity(self, query: np.ndarray, rows: Optional[np.ndarray] = None) -> np.ndarray:
        q = query.astype(np.float32).ravel()
        q /= np.linalg.norm(q) or 1.0
        if rows is not None:
            return np.asarray(self.embeddings[np.sort(rows)], dtype=np.float32) @ q, np.sort(rows)
        # NumPy has no BLAS path for float16, so a direct float16 matmul is
        # slow; upcasting the whole matrix would double its memory. Upcast in
        # chunks instead.
        scores = np.empty(len(self.embeddings), dtype=np.float32)
        for start in range(0, len(self.embeddings), _SEARCH_CHUNK):
            chunk = np.asarray(self.embeddings[start:start + _SEARCH_CHUNK], dtype=np.float32)
            scores[start:start + len(chunk)] = chunk @ q
        return scores

    def search(self, query_embedding: np.ndarray, k: int,
               focus_embedding: Optional[np.ndarray] = None) -> list[tuple[str, float, float]]:
        """Rating-balanced top-k: [(review_id, rating, score)], best first.

        query_embedding: the product. focus_embedding (optional): what this
        persona cares about; re-ranks the product's most relevant reviews so
        a budget shopper and an athlete see different ones."""
        product_scores = self._similarity(query_embedding)
        if focus_embedding is None:
            scores = product_scores
        else:
            pool = min(PRODUCT_POOL, len(product_scores))
            top_product = np.argpartition(-product_scores, pool - 1)[:pool]
            focus_scores, rows = self._similarity(focus_embedding, top_product)
            scores = np.full(len(product_scores), -np.inf, dtype=np.float32)
            scores[rows] = (1 - FOCUS_WEIGHT) * product_scores[rows] + FOCUS_WEIGHT * focus_scores
        pool = min(CANDIDATE_POOL, int(np.isfinite(scores).sum()))
        candidates = np.argpartition(-scores, pool - 1)[:pool]
        candidates = candidates[np.argsort(-scores[candidates])]

        quota = band_quota(k)
        chosen: list[int] = []
        for band, count in quota.items():
            in_band = [i for i in candidates if rating_band(float(self.ratings[i])) == band]
            chosen.extend(in_band[:count])
        # A band can be short of candidates (e.g. a niche product with no
        # 1-star reviews nearby): top up from the best remaining ones.
        for i in candidates:
            if len(chosen) >= k:
                break
            if i not in chosen:
                chosen.append(i)
        chosen.sort(key=lambda i: -scores[i])
        return [(str(self.review_ids[i]), float(self.ratings[i]), float(scores[i])) for i in chosen[:k]]


_index_cache: Optional[ReviewIndex] = None
_encoder_cache = None


def _get_encoder(model_name: str):
    global _encoder_cache
    if _encoder_cache is None:
        from sentence_transformers import SentenceTransformer

        # Query encoding is one short text at a time: CPU is fast enough and
        # keeps the GPU free for the GAN and the LLM.
        _encoder_cache = SentenceTransformer(model_name, device="cpu")
    return _encoder_cache


def _get_index(index_dir: str) -> ReviewIndex:
    global _index_cache
    if _index_cache is None:
        _index_cache = ReviewIndex.load(index_dir)
    return _index_cache


def persona_focus(persona_prompt: str) -> str:
    """The part of a persona that should steer review choice: its behaviour
    ("compares price first, waits for sales", "values performance and
    durability"). Age, region and income labels are noise for this search.
    Seeded personas (scripts/seed_personas.py) put it after "Behavior:"; any
    other prompt is used whole."""
    match = _BEHAVIOR_RE.search(persona_prompt)
    behaviour = (match.group(1) if match else persona_prompt).strip()
    return f"A shoe review from a buyer who {behaviour}"


def fetch_reference_reviews(db: Session, product_description: Optional[str], persona_prompt: str,
                            k: int, index_dir: str) -> list[dict]:
    """[{"rating": float, "text": str}] for the prompt. Raises if the index is
    missing; persona_service decides whether that is fatal (it is not)."""
    from app.models.reference_data import RefReview

    index = _get_index(index_dir)
    encoder = _get_encoder(index.model_name)
    product_q, focus_q = encoder.encode([product_description or "shoes", persona_focus(persona_prompt)],
                                        normalize_embeddings=True)
    hits = index.search(np.asarray(product_q), k, focus_embedding=np.asarray(focus_q))
    ids = [review_id for review_id, _, _ in hits]
    texts = dict(db.query(RefReview.review_id, RefReview.review_text).filter(RefReview.review_id.in_(ids)).all())
    return [{"rating": rating, "text": clean_review_text(texts[review_id])}
            for review_id, rating, _ in hits if review_id in texts]
