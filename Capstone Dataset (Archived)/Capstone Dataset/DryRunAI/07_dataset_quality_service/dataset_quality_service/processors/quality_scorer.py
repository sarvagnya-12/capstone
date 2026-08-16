from __future__ import annotations

from dataset_quality_service.config import QualityRules
from dataset_quality_service.models import DatasetValidationResult


class QualityScorer:
    def __init__(self, rules: QualityRules) -> None:
        self.rules = rules

    def dataset_score(self, result: DatasetValidationResult, missing_relationships: int = 0) -> int:
        score = self.rules.maximum_score
        if result.missing_path:
            score -= self.rules.missing_dataset_penalty
        score -= sum(result.missing_required_fields.values()) * self.rules.missing_required_penalty
        score -= len(result.duplicate_ids) * self.rules.duplicate_penalty
        score -= len(result.broken_product_ids) * self.rules.broken_reference_penalty
        score -= len(result.schema_violations) * self.rules.missing_required_penalty
        score -= missing_relationships * self.rules.missing_relationship_penalty
        return max(self.rules.minimum_score, min(self.rules.maximum_score, score))

    @staticmethod
    def overall(scores: dict[str, int]) -> int:
        if not scores:
            return 0
        return round(sum(scores.values()) / len(scores))

