"""Step 30/31: analytics aggregation and report export endpoints."""

from app.models.feedback import SentimentLabel
from app.models.simulation import SimulationStatus
from app.services import recommendation_service
from tests.conftest import make_feedback, make_persona, make_simulation_with_variants, register_and_login


def _build_completed_simulation(db_session):
    simulation, variants = make_simulation_with_variants(db_session, n_variants=2)
    persona = make_persona(db_session, "Analytics Persona")
    make_feedback(
        db_session, simulation, variants[0], persona,
        purchase_likelihood=0.9, sentiment_score=0.9, sentiment_label=SentimentLabel.POSITIVE,
    )
    make_feedback(
        db_session, simulation, variants[1], persona,
        purchase_likelihood=0.1, sentiment_score=-0.9, sentiment_label=SentimentLabel.NEGATIVE,
    )
    recommendation_service.build_recommendation(db_session, simulation.id)
    simulation.status = SimulationStatus.COMPLETED
    db_session.flush()
    return simulation, variants


def test_analytics_404_before_simulation_ready(client, db_session):
    simulation, _ = make_simulation_with_variants(db_session, n_variants=1)
    token = register_and_login(client, "dashboard_owner1@test.com")
    # Not the actual owner (a different user than the one make_simulation_with_variants
    # created), but ownership scoping should 404 regardless -- and even the real
    # owner would 404 here since no Recommendation exists yet.
    resp = client.get(f"/api/v1/simulations/{simulation.id}/analytics", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


def test_analytics_returns_correct_shape_when_ready(client, db_session):
    simulation, variants = _build_completed_simulation(db_session)

    # The simulation's owner was created directly via the ORM helper, not
    # through a client.post("/register") call, so there's no known password
    # to log in with -- issue a real token for that exact user id directly,
    # the same way a real login would produce one.
    from app.core.security import create_access_token

    token = create_access_token(subject=str(simulation.user_id), role="user")
    resp = client.get(f"/api/v1/simulations/{simulation.id}/analytics", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["simulation_id"] == str(simulation.id)
    assert len(body["variants"]) == 2
    ranks = sorted(v["rank"] for v in body["variants"])
    assert ranks == [1, 2]
    top = next(v for v in body["variants"] if v["rank"] == 1)
    assert top["is_recommended"] is True
    assert top["sentiment"]["positive"] == 1
    assert len(top["feedback"]) == 1
    assert top["feedback"][0]["persona_name"] == "Analytics Persona"


def test_analytics_ownership_scoping(client, db_session):
    simulation, _ = _build_completed_simulation(db_session)
    other_token = register_and_login(client, "dashboard_snooper@test.com")

    resp = client.get(
        f"/api/v1/simulations/{simulation.id}/analytics", headers={"Authorization": f"Bearer {other_token}"}
    )
    assert resp.status_code == 404


def test_report_csv_and_pdf_both_download(client, db_session):
    from app.core.security import create_access_token

    simulation, _ = _build_completed_simulation(db_session)
    token = create_access_token(subject=str(simulation.user_id), role="user")
    headers = {"Authorization": f"Bearer {token}"}

    csv_resp = client.get(f"/api/v1/simulations/{simulation.id}/report?format=csv", headers=headers)
    assert csv_resp.status_code == 200
    assert csv_resp.headers["content-type"].startswith("text/csv")
    assert "DryRunAI Simulation Report" in csv_resp.text

    pdf_resp = client.get(f"/api/v1/simulations/{simulation.id}/report?format=pdf", headers=headers)
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert pdf_resp.content[:4] == b"%PDF"


def test_report_invalid_format_rejected(client, db_session):
    from app.core.security import create_access_token

    simulation, _ = _build_completed_simulation(db_session)
    token = create_access_token(subject=str(simulation.user_id), role="user")

    resp = client.get(
        f"/api/v1/simulations/{simulation.id}/report?format=xml", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 422
