"""Wraps a pretrained NLP sentiment-classification model (Step 23, FR#6). No
model is trained here -- PRD Sec14 leaves "NLP-based sentiment
classification" unnamed; this picks one concrete, documented, publicly
licensed model rather than leaving the choice implicit.

Model: cardiffnlp/twitter-roberta-base-sentiment-latest (RoBERTa-base, fine-
tuned for 3-way sentiment on ~124M tweets, Cardiff NLP Group, MIT-licensed).
Chosen over a 2-class model (e.g. SST-2-tuned DistilBERT) specifically
because it natively outputs negative/neutral/positive, matching this
project's SentimentLabel enum exactly rather than needing a threshold-based
"derive neutral from confidence" workaround. Verified empirically that its
label strings ("positive"/"negative"/"neutral", lowercase) match the enum
values directly.
"""

from functools import lru_cache

from transformers import pipeline

_MODEL_NAME = "cardiffnlp/twitter-roberta-base-sentiment-latest"


@lru_cache(maxsize=1)
def _get_pipeline():
    return pipeline("sentiment-analysis", model=_MODEL_NAME)


def classify_text(text: str) -> tuple[str, float]:
    """Returns (label, confidence) where label is one of "positive"/
    "negative"/"neutral" and confidence is the model's score for that label
    in [0, 1]."""
    result = _get_pipeline()(text, truncation=True)[0]
    return result["label"], float(result["score"])
