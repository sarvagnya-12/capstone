"""Run Stage 7 with a CSV field-size limit that fits real-scale data.

shared/io/tables.py reads with csv.DictReader at Python's default 128 KB field
limit. Stage 6 writes master_products.csv with JSON reference arrays
(review_refs etc.) that grow with the data -- at 496K reviews the largest field
is well past that limit, so Stage 7 crashed on the first row that exceeded it
(_csv.Error: field larger than field limit). Raising the limit here keeps the
frozen shared module untouched; this wrapper is otherwise identical to
`python -m dataset_quality_service`.
"""
from __future__ import annotations

import csv
import sys

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

from dataset_quality_service.pipeline import main  # noqa: E402

if __name__ == "__main__":
    main()
