# Asset Lifecycle

1. Read the frozen product schema.
2. Read `products.csv`.
3. Extract configured image URL columns.
4. Download or copy image bytes.
5. Validate the image.
6. Compute SHA256.
7. Store non-duplicate images under the product ID.
8. Move invalid or duplicate files to quarantine.
9. Export metadata and reports.

