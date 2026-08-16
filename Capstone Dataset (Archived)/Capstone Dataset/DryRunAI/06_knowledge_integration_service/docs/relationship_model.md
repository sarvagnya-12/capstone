# Relationship Model

The master dataset keeps one row per Product ID.

Child records are linked by references:

- `image_refs`
- `review_refs`
- `market_record_refs`
- `product_intelligence_refs`

Each reference includes the source dataset, source, source URL, and collection timestamp when the child dataset provides one.

