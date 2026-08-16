from __future__ import annotations

from typing import Any

from dataset_quality_service.models import DatasetValidationResult


class QualityReportBuilder:
    def build(
        self,
        results: dict[str, DatasetValidationResult],
        scores: dict[str, int],
        manifest_report: dict[str, Any],
        taxonomy_report: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        validation_report = {
            name: {
                "path": result.path,
                "row_count": result.row_count,
                "missing_path": result.missing_path,
                "missing_required_fields": result.missing_required_fields,
                "duplicate_ids": result.duplicate_ids,
                "schema_violations": result.schema_violations,
                "broken_product_ids": result.broken_product_ids,
            }
            for name, result in results.items()
        }
        missing_data_report = {
            name: {
                "missing_values": result.missing_values,
                "missing_dataset": result.missing_path,
            }
            for name, result in results.items()
        }
        relationship_report = {
            "broken_product_ids": {
                name: result.broken_product_ids
                for name, result in results.items()
                if result.broken_product_ids
            },
            "missing_relationships": self._missing_relationships(results),
        }
        dataset_health = {
            "overall_score": round(sum(scores.values()) / len(scores)) if scores else 0,
            "product_quality": scores.get("products", 0),
            "asset_quality": scores.get("images", 0),
            "review_quality": scores.get("reviews", 0),
            "market_quality": scores.get("market", 0),
            "product_intelligence_quality": scores.get("product_intelligence", 0),
            "master_dataset_quality": scores.get("master", 0),
            "manifest_consistency": manifest_report,
            "taxonomy_consistency": taxonomy_report,
        }
        statistics = {
            "row_counts": {name: result.row_count for name, result in results.items()},
            "issue_counts": {name: result.issue_count for name, result in results.items()},
            "scores": scores,
        }
        return {
            "validation_report": validation_report,
            "dataset_health": dataset_health,
            "missing_data_report": missing_data_report,
            "relationship_report": relationship_report,
            "statistics": statistics,
        }

    @staticmethod
    def _missing_relationships(results: dict[str, DatasetValidationResult]) -> dict[str, int]:
        products = results.get("products")
        if products is None:
            return {}
        product_ids = {row.get("product_id") for row in products.rows if row.get("product_id")}
        missing: dict[str, int] = {}
        for name in ("images", "reviews", "market", "product_intelligence"):
            result = results.get(name)
            if result is None or result.missing_path:
                missing[name] = len(product_ids)
                continue
            linked_ids = {row.get("product_id") for row in result.rows if row.get("product_id")}
            missing[name] = len(product_ids - linked_ids)
        return missing

