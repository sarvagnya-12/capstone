from __future__ import annotations

from catalog_builder.collectors.zappos.collector import ZapposCollector


class AmazonCollector(ZapposCollector):
    """Catalog collector for Amazon Reviews 2023 footwear metadata.

    ZapposCollector's parsing is entirely source-agnostic -- its FIELD_ALIASES
    are generic column names and it reads CSV/JSON/JSONL the same way for any
    input -- so the only thing that differs for Amazon is the source label
    recorded on each RawProduct. Subclassing keeps that single difference
    explicit instead of duplicating ~90 lines of identical parsing code.

    The Amazon-specific work (footwear filtering, field renaming, price and
    category extraction) happens upstream in
    _ingestion_tools/prepare_amazon_catalog_rows.py, which emits a CSV in the
    shape these aliases already expect.
    """

    source_name = "amazon"
    auto_register = True
