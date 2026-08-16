"""Shared fixtures for the backend test suite (Step 38).

Uses a real Postgres database (dryrunai_test, on the same server as the dev
DB) rather than SQLite -- this app leans on Postgres-native JSONB and enum
columns throughout, so SQLite would test a meaningfully different code path,
not the real one (matching this step's own plan text). Each test runs inside
one transaction that's rolled back afterward, so tests never leak state into
each other and never touch the real dryrunai database.

Slow/external dependencies are mocked at the two genuinely expensive
boundaries -- loading the real 364MB GAN checkpoint, and calling the real
Anthropic API -- per this step's own guidance ("verifying pipeline mechanics
... not image quality"). Sentiment analysis (a local, already-cached
HuggingFace model) and FID computation are left real: both are fast once
warmed and are exactly the kind of real integration this suite should prove
actually works.
"""

import sys
from pathlib import Path

import pytest
import torch
import torch.nn as nn
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.models  # noqa: E402  imports every model so Base.metadata is fully populated
from app.core.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402

TEST_DB_NAME = "dryrunai_test"


def _test_database_url() -> str:
    base_url = settings.DATABASE_URL.rsplit("/", 1)[0]
    return f"{base_url}/{TEST_DB_NAME}"


def _ensure_test_database_exists() -> None:
    maintenance_url = settings.DATABASE_URL.rsplit("/", 1)[0] + "/postgres"
    engine = create_engine(maintenance_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": TEST_DB_NAME}
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    engine.dispose()


@pytest.fixture(scope="session")
def test_engine():
    _ensure_test_database_exists()
    engine = create_engine(_test_database_url())
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def db_session(test_engine):
    """Isolates each test inside one outer transaction that's always rolled
    back -- but application services call db.commit() internally (e.g.
    register_user, create_product), and a plain "commit ends the
    transaction" session would let those commits escape the rollback and
    leak into dryrunai_test permanently. SQLAlchemy's documented fix: bind
    the session to a SAVEPOINT (begin_nested), and restart a fresh savepoint
    every time the app's own code ends one via commit(), so the outer
    transaction.rollback() at teardown is always what actually undoes
    everything. https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(session, transaction):
        if transaction.nested and not transaction._parent.nested:
            session.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(autouse=True)
def isolated_storage_root(tmp_path, monkeypatch):
    """Product/variant image uploads write real files via storage_service,
    which reads settings.STORAGE_ROOT at call time -- not transactional, so
    db_session's rollback can't undo them. Without this, every test touching
    an upload would leave real files under backend/storage/ with nothing to
    clean them up. Autouse so no test has to remember to ask for it."""
    monkeypatch.setattr(settings, "STORAGE_ROOT", str(tmp_path))


@pytest.fixture()
def client(db_session):
    from fastapi.testclient import TestClient

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


def register_and_login(client, email: str, password: str = "TestPass123!", org_name: str = "Test Org") -> str:
    """Returns a bearer token for a freshly-registered user."""
    resp = client.post(
        "/api/v1/auth/register", json={"org_name": org_name, "email": email, "password": password}
    )
    assert resp.status_code == 201, resp.text
    resp = client.post(
        "/api/v1/auth/login", data={"username": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def make_persona(db, name="Test Persona", lifestyle="urban"):
    import uuid as _uuid

    from app.models.persona import Persona, PersonaSource

    persona = Persona(
        template_key=f"key-{_uuid.uuid4()}",
        name=name,
        age_min=20,
        age_max=30,
        income_segment="mid",
        lifestyle=lifestyle,
        region="US",
        behavior_traits={},
        prompt_template=f"You are {name}, a {lifestyle} shopper.",
        source=PersonaSource.SEEDED,
    )
    db.add(persona)
    db.flush()
    return persona


def make_simulation_with_variants(db, n_variants=2, max_iterations=3):
    """Hand-builds a User -> Product -> Simulation -> [ProductVariant] chain
    directly against the ORM, bypassing the API/GAN entirely -- most service
    tests only care about the data shape, not how it got there."""
    import uuid as _uuid

    from app.core.security import hash_password
    from app.models.product import Product
    from app.models.product_variant import ProductVariant
    from app.models.simulation import Simulation
    from app.models.user import User, UserRole

    user = User(
        org_name="Test Org", email=f"{_uuid.uuid4()}@test.com", hashed_password=hash_password("x"), role=UserRole.USER
    )
    db.add(user)
    db.flush()

    product = Product(user_id=user.id, name="P", description="d", category="c", original_image_path="x.jpg")
    db.add(product)
    db.flush()

    simulation = Simulation(
        product_id=product.id,
        user_id=user.id,
        pricing_strategy={"tiers": [{"tier_name": "standard", "price": 10.0}]},
        target_demographic={},
        max_iterations=max_iterations,
    )
    db.add(simulation)
    db.flush()

    variants = []
    for i in range(n_variants):
        variant = ProductVariant(
            product_id=product.id,
            simulation_id=simulation.id,
            image_path=f"variant-{i}.jpg",
            attributes={"i": i},
            generation_method="gan_latent_variation",
        )
        db.add(variant)
        variants.append(variant)
    db.flush()

    return simulation, variants


def make_feedback(db, simulation, variant, persona, *, iteration_number=0, purchase_likelihood=0.5,
                   sentiment_label=None, sentiment_score=None, qualitative_text="A reaction.",
                   consistency_variance=None, risk_flags=None):
    from app.models.feedback import Feedback

    feedback = Feedback(
        simulation_id=simulation.id,
        variant_id=variant.id,
        persona_id=persona.id,
        qualitative_text=qualitative_text,
        purchase_likelihood=purchase_likelihood,
        iteration_number=iteration_number,
        sentiment_label=sentiment_label,
        sentiment_score=sentiment_score,
        consistency_variance=consistency_variance,
        risk_flags=risk_flags,
    )
    db.add(feedback)
    db.flush()
    return feedback


@pytest.fixture()
def auth_headers(client):
    token = register_and_login(client, "fixture_user@test.com")
    return {"Authorization": f"Bearer {token}"}


class FakeLLMProvider:
    """Deterministic-but-varied stand-in for AnthropicProvider (Step 20's
    Protocol makes this a drop-in swap). Alternates sentiment/likelihood by a
    counter rather than returning identical output every call, so tests that
    depend on variation (e.g. picking a top scorer) have something real to
    select between."""

    def __init__(self):
        self.call_count = 0

    def complete(self, prompt: str) -> str:
        self.call_count += 1
        if self.call_count % 3 == 0:
            return '{"reaction_text": "Not for me, feels overpriced.", "purchase_likelihood": 0.1}'
        return '{"reaction_text": "I really like this, would consider buying.", "purchase_likelihood": 0.8}'


@pytest.fixture()
def fake_llm_provider(monkeypatch):
    fake = FakeLLMProvider()
    monkeypatch.setattr("app.services.persona_service.get_llm_provider", lambda: fake)
    return fake


class _FakeGenerator(nn.Module):
    """Tiny stand-in for the real StyleGAN2-ADA generator (Step 15) -- same
    interface (z_dim/c_dim, callable as generator(z, c, truncation_psi=...,
    noise_mode=...) -> (1, 3, H, W) tensor in [-1, 1]) but with a handful of
    random weights instead of a 364MB checkpoint, so tests don't pay for a
    real forward pass through a production-sized network."""

    def __init__(self):
        super().__init__()
        self.z_dim = 8
        self.c_dim = 0
        self.linear = nn.Linear(self.z_dim, 3 * 32 * 32)

    def forward(self, z: torch.Tensor, c: torch.Tensor, truncation_psi: float = 1.0, noise_mode: str = "const"):
        out = torch.tanh(self.linear(z))
        return out.view(1, 3, 32, 32)


@pytest.fixture()
def fake_gan_generator(monkeypatch):
    fake = _FakeGenerator()
    fake.eval()
    monkeypatch.setattr("app.ml.gan.inference._get_generator", lambda: fake)
    return fake


@pytest.fixture()
def committed_client(test_engine, monkeypatch):
    """For the one case db_session/client can't cover: simulation_orchestrator
    deliberately opens its own SessionLocal() (a separate connection) since
    it runs as a FastAPI BackgroundTasks job outside the request-scoped
    get_db() lifecycle (Step 28's own architecture decision). A savepoint on
    ONE connection is invisible to a second, independent connection -- real
    transaction isolation, not a testing bug -- so this fixture can't use the
    rollback trick db_session relies on. Instead: real commits against
    dryrunai_test (never the real dryrunai DB, still test_engine), with
    every table truncated at teardown. Both the request-scoped session and
    simulation_orchestrator's own SessionLocal are pointed at the same
    test_engine, exactly mirroring how the two connections relate in
    production."""
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker

    from app.services import simulation_orchestrator

    TestSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(simulation_orchestrator, "SessionLocal", TestSessionLocal)

    def _override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)

    with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
