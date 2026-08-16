"""Step 13: dataset pipeline ingestion script. Builds a fully synthetic
pipeline_root (pytest's tmp_path) with minimal schema/CSV fixtures rather
than depending on the real archived pipeline's exact file layout, or writing
anything into its directories (matching this step's own precaution: never
write test fixtures into the archived pipeline's own directories).

ingest() opens its own engine via settings.DATABASE_URL rather than
accepting a session, so it's redirected to the test database the same way
committed_client redirects simulation_orchestrator -- both are the
BackgroundTasks-style "opens its own connection" case db_session's
savepoint trick can't reach.
"""

import csv
import json
from pathlib import Path

import pytest

from app.core.config import settings
from app.models.reference_data import RefProduct


def _write_products_schema(schemas_dir: Path) -> None:
    schemas_dir.mkdir(parents=True, exist_ok=True)
    schema = {
        "columns": [
            {"name": "product_id", "required": True},
            {"name": "brand", "required": True},
            {"name": "model", "required": True},
            {"name": "category", "required": True},
            {"name": "source", "required": True},
            {"name": "provenance", "required": True},
            {"name": "relationship_counts", "required": True},
            {"name": "status", "required": True},
            {"name": "retail_price", "required": False},
            {"name": "image_refs", "required": False},
        ]
    }
    (schemas_dir / "master_products_schema.json").write_text(json.dumps(schema))


def _write_market_schema(schemas_dir: Path) -> None:
    schema = {
        "columns": [
            {"name": "market_record_id", "required": True},
            {"name": "product_id", "required": True},
            {"name": "source", "required": True},
            {"name": "market_type", "required": True},
            {"name": "price_type", "required": True},
            {"name": "availability", "required": True},
            {"name": "last_updated", "required": True},
            {"name": "status", "required": True},
        ]
    }
    (schemas_dir / "market_schema.json").write_text(json.dumps(schema))


def _write_products_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "product_id", "brand", "model", "category", "source",
        "provenance", "relationship_counts", "status", "retail_price", "image_refs",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


@pytest.fixture()
def synthetic_pipeline_root(tmp_path):
    schemas_dir = tmp_path / "schemas"
    _write_products_schema(schemas_dir)
    _write_market_schema(schemas_dir)

    _write_products_csv(
        tmp_path / "datasets" / "master" / "master_products.csv",
        [
            {
                "product_id": "p1", "brand": "Acme", "model": "Runner", "category": "footwear",
                "source": "test", "provenance": '{"origin": "synthetic"}',
                "relationship_counts": '{"reviews": 0}', "status": "active",
                "retail_price": "59.99", "image_refs": '["img1", "img2"]',
            },
        ],
    )

    # market.csv deliberately missing "availability" -- tests that this
    # file's failure doesn't block master_products.csv from ingesting.
    market_dir = tmp_path / "datasets" / "master"
    market_dir.mkdir(parents=True, exist_ok=True)
    with (market_dir / "market.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["market_record_id", "product_id", "source", "market_type", "price_type", "last_updated", "status"])
        writer.writeheader()
        writer.writerow({
            "market_record_id": "m1", "product_id": "p1", "source": "test",
            "market_type": "retail", "price_type": "msrp", "last_updated": "2026-01-01T00:00:00",
            "status": "active",
        })

    return tmp_path


@pytest.fixture()
def ingestion_module(test_engine, monkeypatch):
    """ingest_dataset_pipeline.py builds its own engine from
    settings.DATABASE_URL -- point that at the test database for the
    duration of the test, exactly like committed_client does for the
    orchestrator's own SessionLocal."""
    import sys

    from tests.conftest import _test_database_url

    repo_root = Path(__file__).resolve().parents[2]
    monkeypatch.syspath_prepend(str(repo_root / "scripts"))
    # str(engine.url) masks the password ("***") by default -- must reuse the
    # same URL string test_engine was actually built from, not re-derive it
    # from the engine object.
    monkeypatch.setattr(settings, "DATABASE_URL", _test_database_url())

    sys.modules.pop("ingest_dataset_pipeline", None)
    import ingest_dataset_pipeline

    yield ingest_dataset_pipeline

    # Real commits (ingest() manages its own engine/session) -- clean up
    # explicitly rather than relying on a rollback that never applies here.
    with test_engine.begin() as conn:
        conn.execute(RefProduct.__table__.delete())
        from app.models.reference_data import RefMarket
        conn.execute(RefMarket.__table__.delete())


def test_ingest_valid_file_upserts_rows(synthetic_pipeline_root, ingestion_module, test_engine):
    results, failures = ingestion_module.ingest(synthetic_pipeline_root, "test_v1", overrides={})

    assert results["ref_products"] == 1
    assert "ref_products" not in failures

    from sqlalchemy.orm import Session
    with Session(test_engine) as session:
        product = session.get(RefProduct, "p1")
        assert product.brand == "Acme"
        assert product.retail_price == 59.99  # coerced to float
        assert product.image_refs == ["img1", "img2"]  # coerced from JSON string to a real list
        assert product.source_dataset_version == "test_v1"


def test_ingest_is_idempotent_on_rerun(synthetic_pipeline_root, ingestion_module, test_engine):
    ingestion_module.ingest(synthetic_pipeline_root, "v1", overrides={})

    # Change the source data and re-run -- should update in place, not duplicate.
    _write_products_csv(
        synthetic_pipeline_root / "datasets" / "master" / "master_products.csv",
        [
            {
                "product_id": "p1", "brand": "Acme", "model": "Runner", "category": "footwear",
                "source": "test", "provenance": '{"origin": "synthetic"}',
                "relationship_counts": '{"reviews": 0}', "status": "active",
                "retail_price": "49.99", "image_refs": '["img1"]',
            },
        ],
    )
    results, _ = ingestion_module.ingest(synthetic_pipeline_root, "v2", overrides={})

    assert results["ref_products"] == 1

    from sqlalchemy.orm import Session
    with Session(test_engine) as session:
        count = session.query(RefProduct).count()
        assert count == 1  # updated in place, not duplicated
        product = session.get(RefProduct, "p1")
        assert product.retail_price == 49.99
        assert product.source_dataset_version == "v2"


def test_ingest_isolates_failures_per_file(synthetic_pipeline_root, ingestion_module):
    """market.csv is missing a required column ("availability") -- that
    failure must not prevent master_products.csv from ingesting."""
    results, failures = ingestion_module.ingest(synthetic_pipeline_root, "v1", overrides={})

    assert results["ref_products"] == 1
    assert "ref_market" in failures
    assert results["ref_market"] == 0


def test_ingest_missing_file_reports_zero_without_crashing(tmp_path, ingestion_module):
    (tmp_path / "schemas").mkdir()
    results, failures = ingestion_module.ingest(tmp_path, "v1", overrides={})

    assert all(count == 0 for count in results.values())
    assert failures == {}  # a missing file is a documented skip, not a failure
