from __future__ import annotations

import unittest
from pathlib import Path

from shared.collectors import BaseCollector, CollectorFactory, CollectorRegistry


class DemoCollector(BaseCollector):
    service_name = "demo_service"
    source_name = "demo_source"
    auto_register = False

    def collect(self, input_path: Path) -> list[str]:
        return [str(input_path)]


class SharedCollectorFrameworkTests(unittest.TestCase):
    def test_registry_and_factory_create_collector(self) -> None:
        registry = CollectorRegistry()
        registry.register(DemoCollector)
        collector = CollectorFactory(registry).create("demo_service", "demo_source")
        self.assertIsInstance(collector, DemoCollector)
        self.assertEqual(collector.collect(Path("input.csv")), ["input.csv"])


if __name__ == "__main__":
    unittest.main()
