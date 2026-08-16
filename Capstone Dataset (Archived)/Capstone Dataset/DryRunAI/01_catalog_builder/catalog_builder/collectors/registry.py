from __future__ import annotations

from catalog_builder.collectors.base import BaseCollector


class CollectorRegistry:
    def __init__(self) -> None:
        self._collectors: dict[str, type[BaseCollector]] = {}

    def register(self, collector_cls: type[BaseCollector]) -> None:
        self._collectors[collector_cls.source_name] = collector_cls

    def create(self, source_name: str) -> BaseCollector:
        try:
            return self._collectors[source_name]()
        except KeyError as exc:
            available = ", ".join(sorted(self._collectors))
            raise ValueError(f"Unknown collector '{source_name}'. Available collectors: {available}") from exc

    def available(self) -> list[str]:
        return sorted(self._collectors)

