from __future__ import annotations

from review_builder.collectors.base import BaseReviewCollector


class ReviewCollectorRegistry:
    def __init__(self) -> None:
        self._collectors: dict[str, type[BaseReviewCollector]] = {}

    def register(self, collector_cls: type[BaseReviewCollector]) -> None:
        self._collectors[collector_cls.source_name] = collector_cls

    def create(self, source_name: str) -> BaseReviewCollector:
        try:
            return self._collectors[source_name.lower()]()
        except KeyError as exc:
            available = ", ".join(sorted(self._collectors))
            raise ValueError(f"Unknown review collector '{source_name}'. Available collectors: {available}") from exc

