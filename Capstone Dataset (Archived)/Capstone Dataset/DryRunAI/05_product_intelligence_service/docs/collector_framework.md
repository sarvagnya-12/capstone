# Product Intelligence Collector Framework

Product Intelligence collectors are plugin collectors built on `shared.collectors`.

Each collector maps source rows to `RawIntelligenceRecord`. Collectors do not normalize, validate, deduplicate, infer, or export data.

The shared registry discovers configured plugin modules. The pipeline requests source collectors through `CollectorFactory`.

