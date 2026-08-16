from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from catalog_builder.config.settings import MatchingConfig
from catalog_builder.models import NormalizedProduct


@dataclass(frozen=True, slots=True)
class MatchDecision:
    status: str
    confidence: float
    duplicate_of: str | None = None


class DuplicateMatcher:
    def __init__(self, config: MatchingConfig) -> None:
        self.config = config

    def classify(self, candidate: NormalizedProduct, existing: list[NormalizedProduct]) -> MatchDecision:
        best_product: NormalizedProduct | None = None
        best_score = 0.0
        for product in existing:
            score = self.score(candidate, product)
            if score > best_score:
                best_score = score
                best_product = product
        if best_product is None:
            return MatchDecision(status="new", confidence=1.0)
        if best_score >= self.config.high_confidence_threshold:
            return MatchDecision(status="duplicate_merged", confidence=best_score, duplicate_of=best_product.product_id)
        if best_score >= self.config.medium_confidence_threshold:
            return MatchDecision(status="manual_review", confidence=best_score, duplicate_of=best_product.product_id)
        return MatchDecision(status="new", confidence=1.0 - best_score)

    def score(self, left: NormalizedProduct, right: NormalizedProduct) -> float:
        if left.fingerprint == right.fingerprint:
            return 1.0
        brand_score = self._exact(left.brand, right.brand)
        category_score = self._exact(left.category, right.category)
        gender_score = self._exact(left.gender, right.gender)
        model_score = self._ratio(left.model, right.model)
        return (brand_score * 0.28) + (model_score * 0.42) + (category_score * 0.2) + (gender_score * 0.1)

    @staticmethod
    def _exact(left: str | None, right: str | None) -> float:
        if not left or not right:
            return 0.0
        return 1.0 if left.lower() == right.lower() else 0.0

    @staticmethod
    def _ratio(left: str | None, right: str | None) -> float:
        if not left or not right:
            return 0.0
        return SequenceMatcher(None, left.lower(), right.lower()).ratio()

