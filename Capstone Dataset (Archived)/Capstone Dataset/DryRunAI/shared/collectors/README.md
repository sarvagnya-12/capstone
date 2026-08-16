# Shared Collector Framework

All DryRunAI collectors inherit from `shared.collectors.BaseCollector`.

The interface defines a standard lifecycle:

- `initialize`
- `collect`
- `validate`
- `normalize`
- `export`
- `cleanup`
- `report`

Collectors register automatically when their class is imported and declares `service_name` and `source_name`.

Services should request collectors through `CollectorFactory` instead of directly instantiating collector classes. `CollectorRegistry.discover()` imports plugin modules so future services can load collectors from configuration without changing service code.
