"""Ingest the dataset-extraction pipeline's frozen output files into this
application's read-only ref_* tables (backend/app/models/reference_data.py).

Usage:
    python scripts/ingest_dataset_pipeline.py \
        --pipeline-root "../Capstone Dataset (Archived)/Capstone Dataset/DryRunAI" \
        --dataset-version catalog_v1

Reads, from <pipeline-root> (override any individual path if the pipeline's
actual output location differs from these defaults):
    datasets/master/master_products.csv        -> ref_products
    datasets/master/image_metadata.csv          -> ref_images
    datasets/master/reviews.csv                 -> ref_reviews
    datasets/master/market.csv                  -> ref_market
    datasets/master/product_intelligence.csv    -> ref_product_intelligence

Each file's columns are validated against the pipeline's own schemas/*.json
contract before ingesting -- a required column missing aborts ingestion for
that file (not the whole run) rather than silently importing malformed data.
Rows are upserted by the pipeline's natural primary key (product_id,
review_id, etc.), so re-running with the same source is idempotent.

CURRENT DATA STATE (as of this writing): the pipeline has never been run
end-to-end -- project_manifest.json shows every record count at 0. Only tiny
raw, pre-normalization source fixtures exist under datasets/*/raw/ (e.g.
sample_zappos.csv), and those are NOT in the ref_* output schema this script
reads (they're Services 01/03/04/05's *inputs*, not the pipeline's *outputs*).
Running against a real --pipeline-root today will therefore correctly report
0 rows for every table with a "file not found" note -- that is expected, not
a bug, and requires no code change once the pipeline is actually run: just
re-point --pipeline-root (and the per-file overrides, if paths differ from
the defaults above) at the populated output.
"""

import argparse
import csv
import json
import sys
from datetime import date as date_cls
from datetime import datetime, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.dialects.postgresql import JSONB  # noqa: E402
from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.models.reference_data import (  # noqa: E402
    RefImage,
    RefMarket,
    RefProduct,
    RefProductIntelligence,
    RefReview,
)

# (cli override dest, schema filename, default relative path, model, pk column)
DATASETS = [
    ("master_products", "master_products_schema.json", "datasets/master/master_products.csv", RefProduct, "product_id"),
    ("image_metadata", "images_schema.json", "datasets/master/image_metadata.csv", RefImage, "image_id"),
    ("reviews", "reviews_schema.json", "datasets/master/reviews.csv", RefReview, "review_id"),
    ("market", "market_schema.json", "datasets/master/market.csv", RefMarket, "market_record_id"),
    (
        "product_intelligence",
        "product_intelligence_schema.json",
        "datasets/master/product_intelligence.csv",
        RefProductIntelligence,
        "intelligence_record_id",
    ),
]


class SchemaValidationError(Exception):
    pass


def load_schema_columns(pipeline_root: Path, schema_filename: str) -> list[dict]:
    schema_path = pipeline_root / "schemas" / schema_filename
    with schema_path.open(encoding="utf-8") as f:
        return json.load(f)["columns"]


def validate_csv_columns(csv_path: Path, schema_columns: list[dict]) -> None:
    required = {c["name"] for c in schema_columns if c.get("required")}
    with csv_path.open(encoding="utf-8", newline="") as f:
        actual = set(csv.DictReader(f).fieldnames or [])
    missing = required - actual
    if missing:
        raise SchemaValidationError(f"{csv_path}: missing required columns per schema: {sorted(missing)}")


def read_csv_rows(csv_path: Path) -> list[dict]:
    with csv_path.open(encoding="utf-8", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _coerce_value(value: str, column):
    if isinstance(column.type, JSONB):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    try:
        py_type = column.type.python_type
    except NotImplementedError:
        return value
    try:
        if py_type is int:
            return int(value)
        if py_type is float:
            return float(value)
        if py_type is bool:
            return str(value).strip().lower() in {"true", "1", "yes"}
        if py_type is date_cls:
            return date_cls.fromisoformat(value)
        if py_type is datetime:
            return datetime.fromisoformat(value)
        return value
    except (TypeError, ValueError):
        return value


def _coerce_row(row: dict, model, extra: dict) -> dict:
    columns = {c.name: c for c in model.__table__.columns}
    result: dict = {}
    for key, value in row.items():
        if key not in columns:
            continue
        result[key] = None if value in ("", None) else _coerce_value(value, columns[key])
    result.update(extra)
    return result


def upsert_rows(db: Session, model, rows: list[dict], pk_column: str, extra: dict) -> int:
    if not rows:
        return 0
    values = [_coerce_row(row, model, extra) for row in rows]
    stmt = pg_insert(model).values(values)
    update_columns = {c.name: getattr(stmt.excluded, c.name) for c in model.__table__.columns if c.name != pk_column}
    stmt = stmt.on_conflict_do_update(index_elements=[pk_column], set_=update_columns)
    db.execute(stmt)
    db.commit()
    return len(values)


def ingest(pipeline_root: Path, dataset_version: str, overrides: dict) -> dict:
    engine = create_engine(settings.DATABASE_URL)
    results = {}
    failures: dict[str, str] = {}

    with Session(engine) as db:
        for cli_dest, schema_filename, default_relative_path, model, pk_column in DATASETS:
            table_name = model.__tablename__
            csv_path = Path(overrides[cli_dest]) if overrides.get(cli_dest) else pipeline_root / default_relative_path

            if not csv_path.exists():
                print(f"[skip] {table_name}: no file at {csv_path} (pipeline hasn't produced this output yet)")
                results[table_name] = 0
                continue

            # A schema mismatch or bad row in one file must not block ingestion of
            # the other four, unrelated files -- isolate and report, don't abort.
            try:
                schema_columns = load_schema_columns(pipeline_root, schema_filename)
                validate_csv_columns(csv_path, schema_columns)

                rows = read_csv_rows(csv_path)
                count = upsert_rows(
                    db,
                    model,
                    rows,
                    pk_column,
                    extra={"ingested_at": datetime.now(timezone.utc), "source_dataset_version": dataset_version},
                )
                print(f"[ok] {table_name}: upserted {count} rows from {csv_path}")
                results[table_name] = count
            except Exception as e:
                db.rollback()
                print(f"[FAIL] {table_name}: {e}")
                failures[table_name] = str(e)
                results[table_name] = 0

    if failures:
        print(f"\n{len(failures)} of {len(DATASETS)} table(s) failed: {', '.join(failures)}")

    return results, failures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pipeline-root", required=True, help="Path to Capstone Dataset (Archived)/Capstone Dataset/DryRunAI")
    parser.add_argument("--dataset-version", default="unknown", help="Recorded in source_dataset_version, e.g. catalog_v1")
    for cli_dest, _, default_relative_path, _, _ in DATASETS:
        parser.add_argument(
            f"--{cli_dest.replace('_', '-')}",
            dest=cli_dest,
            default=None,
            help=f"Override path (default: <pipeline-root>/{default_relative_path})",
        )
    args = parser.parse_args()

    pipeline_root = Path(args.pipeline_root).resolve()
    if not pipeline_root.is_dir():
        raise SystemExit(f"--pipeline-root does not exist: {pipeline_root}")

    overrides = {cli_dest: getattr(args, cli_dest) for cli_dest, _, _, _, _ in DATASETS}
    results, failures = ingest(pipeline_root, args.dataset_version, overrides)
    total = sum(results.values())
    print(f"\nDone. {total} total rows ingested across {len(results)} tables.")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
