from __future__ import annotations

import importlib
from typing import Any

from shared.collectors.base_collector import BaseCollector


class CollectorRegistry:
    def __init__(self) -> None:
        self._collectors: dict[str, dict[str, type[BaseCollector]]] = {}

    def register(self, collector_cls: type[BaseCollector]) -> None:
        service_name = collector_cls.service_name.lower()
        source_name = collector_cls.source_name.lower()
        self._collectors.setdefault(service_name, {})[source_name] = collector_cls

    def create(self, service_name: str, source_name: str, config: Any | None = None) -> BaseCollector:
        collector_cls = self.get(service_name, source_name)
        collector = collector_cls()
        collector.initialize(config)
        return collector

    def get(self, service_name: str, source_name: str) -> type[BaseCollector]:
        service_collectors = self._collectors.get(service_name.lower(), {})
        try:
            return service_collectors[source_name.lower()]
        except KeyError as exc:
            available = ", ".join(sorted(service_collectors))
            raise ValueError(f"Unknown collector '{source_name}' for service '{service_name}'. Available collectors: {available}") from exc

    def available(self, service_name: str | None = None) -> dict[str, list[str]] | list[str]:
        if service_name is not None:
            return sorted(self._collectors.get(service_name.lower(), {}))
        return {service: sorted(collectors) for service, collectors in sorted(self._collectors.items())}

    def discover(self, modules: list[str]) -> None:
        for module in modules:
            importlib.import_module(module)


global_collector_registry = CollectorRegistry()

