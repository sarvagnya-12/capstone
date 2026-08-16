"""Step 39: the full documented user journey (Fig 6.4 Activity Diagram) as
one continuous flow -- register -> login -> upload product -> configure
scenario -> run simulation -> poll to completion -> view analytics ->
download report -- exercising at least one full iteration of the
optimization loop, not just individually-passing unit tests.

Uses committed_client (see conftest.py) rather than the fast rollback-
isolated client/db_session fixtures: simulation_orchestrator runs as a real
FastAPI BackgroundTasks job with its own SessionLocal() connection, which a
savepoint on a different connection is structurally invisible to. Real GAN
checkpoint loading and the real Anthropic API are still mocked (same as
Step 38) -- this test proves the phases integrate correctly, not model
quality.
"""

import io

from PIL import Image


def test_full_user_journey_end_to_end(committed_client, fake_gan_generator, fake_llm_provider, test_engine):
    client = committed_client

    # 1. Register + login
    register_resp = client.post(
        "/api/v1/auth/register",
        json={"org_name": "E2E Org", "email": "e2e@test.com", "password": "TestPass123!"},
    )
    assert register_resp.status_code == 201

    login_resp = client.post("/api/v1/auth/login", data={"username": "e2e@test.com", "password": "TestPass123!"})
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Upload product
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color=(120, 60, 200)).save(buf, format="JPEG")
    buf.seek(0)
    upload_resp = client.post(
        "/api/v1/products",
        headers=headers,
        data={"name": "E2E Sneaker", "description": "Full pipeline test product", "category": "footwear"},
        files={"image": ("product.jpg", buf.read(), "image/jpeg")},
    )
    assert upload_resp.status_code == 201
    product_id = upload_resp.json()["id"]

    # In production this precondition is satisfied by having already run
    # scripts/seed_personas.py once (documented setup step) -- without it,
    # select_representative_personas() returns an empty list, every
    # persona-reaction round produces zero Feedback rows, and
    # build_recommendation() has nothing to work with. Seed directly via
    # the ORM against the same test_engine committed_client points at.
    from sqlalchemy.orm import Session as _Session

    from tests.conftest import make_persona

    with _Session(test_engine) as seed_db:
        make_persona(seed_db, "E2E Test Persona", lifestyle="urban")
        seed_db.commit()

    # 3. Configure scenario + run simulation (max_iterations=2 to exercise
    # at least one full loop of the optimization iteration, per this step's
    # own completion criteria).
    create_resp = client.post(
        "/api/v1/simulations",
        headers=headers,
        json={
            "product_id": product_id,
            "pricing_strategy": [{"tier_name": "standard", "price": 79.99}],
            "target_demographic": {"age_min": 18, "age_max": 35, "lifestyle": "urban"},
            "promotional_messaging": "Full pipeline E2E test",
            "variant_count": 2,
            "max_iterations": 2,
        },
    )
    assert create_resp.status_code == 202
    simulation_id = create_resp.json()["id"]

    # 4. Poll to completion. TestClient executes BackgroundTasks inline
    # before returning the POST response, so this is expected to already be
    # done -- polling anyway is the defensive, not-relying-on-that-detail way
    # to wait, and mirrors exactly what SimulationRunPage.tsx does for real.
    status = None
    for _ in range(20):
        status_resp = client.get(f"/api/v1/simulations/{simulation_id}/status", headers=headers)
        assert status_resp.status_code == 200
        status = status_resp.json()["status"]
        if status in ("completed", "failed"):
            break
    assert status == "completed", f"simulation did not complete (status={status})"

    status_body = client.get(f"/api/v1/simulations/{simulation_id}/status", headers=headers).json()
    assert status_body["iteration_count"] == 2  # both rounds ran, respecting max_iterations

    # 5. View analytics -- exactly what DashboardPage.tsx calls.
    analytics_resp = client.get(f"/api/v1/simulations/{simulation_id}/analytics", headers=headers)
    assert analytics_resp.status_code == 200
    analytics = analytics_resp.json()
    assert analytics["final_iteration"] == 1  # 0-indexed: round 2 of 2
    assert len(analytics["variants"]) == 2  # only the final round's variants, not all 4 generated
    assert analytics["recommended_variant_id"] in {v["variant_id"] for v in analytics["variants"]}
    for variant in analytics["variants"]:
        assert variant["fid_score"] is not None
        assert len(variant["feedback"]) > 0

    # 6. Recommendation retrieval (Step 29's own endpoint).
    rec_resp = client.get(f"/api/v1/simulations/{simulation_id}/recommendation", headers=headers)
    assert rec_resp.status_code == 200
    assert rec_resp.json()["recommended_variant_id"] == analytics["recommended_variant_id"]

    # 7. Download reports.
    csv_resp = client.get(f"/api/v1/simulations/{simulation_id}/report?format=csv", headers=headers)
    assert csv_resp.status_code == 200
    pdf_resp = client.get(f"/api/v1/simulations/{simulation_id}/report?format=pdf", headers=headers)
    assert pdf_resp.status_code == 200
    assert pdf_resp.content[:4] == b"%PDF"

    # Cross-check final DB state directly against the database, not just
    # trusting the API's own responses -- the same discipline used
    # throughout manual verification all session: 2 rounds x 2 variants = 4
    # variants total, but only round 2's 2 variants have a recommendation
    # entry, and every variant across both rounds has real feedback rows.
    import uuid as uuid_mod

    from sqlalchemy.orm import Session

    from app.models.feedback import Feedback
    from app.models.product_variant import ProductVariant
    from app.models.recommendation import Recommendation

    with Session(test_engine) as db:
        sim_uuid = uuid_mod.UUID(simulation_id)
        variants = db.query(ProductVariant).filter(ProductVariant.simulation_id == sim_uuid).all()
        assert len(variants) == 4  # 2 rounds x 2 variants/round

        feedback_rows = db.query(Feedback).filter(Feedback.simulation_id == sim_uuid).all()
        assert len(feedback_rows) == 4  # 2 variants x 1 persona x 2 rounds (default persona sample)

        recommendation = db.query(Recommendation).filter(Recommendation.simulation_id == sim_uuid).one()
        assert str(recommendation.recommended_variant_id) == analytics["recommended_variant_id"]
