# Review Collector Interface

Each collector maps source-specific review rows into `RawReview`.

Collectors should not normalize, validate, deduplicate, or export data. Those concerns belong to processors, validators, and exporters.

To add a source:

1. Add a collector module under `review_builder/collectors/`.
2. Subclass `BaseReviewCollector`.
3. Set `source_name`.
4. Return `RawReview` objects from `collect()`.
5. Register the collector in `build_registry()`.

