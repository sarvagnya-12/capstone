from __future__ import annotations

from typing import Any

from shared.collectors.base_collector import BaseCollector
from shared.collectors.collector_registry import CollectorRegistry, global_collector_registry


class CollectorFactory:
    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        self.registry = registry or global_collector_registry

    def create_from_config(self, service_name: str, collector_config: dict[str, Any]) -> BaseCollector:
        source_name = str(collector_config["source"])
        return self.registry.create(service_name, source_name, collector_config)

    def create(self, service_name: str, source_name: str, config: Any | None = None) -> BaseCollector:
        return self.registry.create(service_name, source_name, config)

