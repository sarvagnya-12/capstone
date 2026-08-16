from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, ClassVar


class BaseCollector(ABC):
    """Shared lifecycle interface for all DryRunAI collectors."""

    service_name: ClassVar[str] = "shared"
    source_name: ClassVar[str]
    auto_register: ClassVar[bool] = True

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if getattr(cls, "auto_register", True) and not getattr(cls, "__abstractmethods__", None):
            from shared.collectors.collector_registry import global_collector_registry

            source_name = getattr(cls, "source_name", None)
            service_name = getattr(cls, "service_name", None)
            if source_name and service_name:
                global_collector_registry.register(cls)

    def initialize(self, config: Any | None = None) -> None:
        self.config = config

    @abstractmethod
    def collect(self, input_path: Path) -> list[Any]:
        """Collect raw records from a source."""

    def validate(self, records: list[Any]) -> list[Any]:
        return records

    def normalize(self, records: list[Any]) -> list[Any]:
        return records

    def export(self, records: list[Any], output_path: Path) -> None:
        raise NotImplementedError("Collectors should not export unless a service explicitly supports it.")

    def cleanup(self) -> None:
        return None

    def report(self) -> dict[str, Any]:
        return {}

