"""Step 37/40: admin-only visibility and the real access-control boundary
(the backend's 403 -- not just the frontend's route guard)."""

from app.services.auth_service import promote_to_admin
from tests.conftest import register_and_login


def test_admin_endpoints_reachable_by_admin(client, db_session):
    register_and_login(client, "willbeadmin@test.com")
    promote_to_admin(db_session, "willbeadmin@test.com")
    login_resp = client.post(
        "/api/v1/auth/login", data={"username": "willbeadmin@test.com", "password": "TestPass123!"}
    )
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    users_resp = client.get("/api/v1/admin/users", headers=headers)
    assert users_resp.status_code == 200
    assert any(u["email"] == "willbeadmin@test.com" for u in users_resp.json())

    sims_resp = client.get("/api/v1/admin/simulations", headers=headers)
    assert sims_resp.status_code == 200


def test_admin_endpoints_reject_regular_user(client, auth_headers):
    resp = client.get("/api/v1/admin/users", headers=auth_headers)
    assert resp.status_code == 403

    resp = client.get("/api/v1/admin/simulations", headers=auth_headers)
    assert resp.status_code == 403


def test_admin_endpoints_reject_unauthenticated(client):
    resp = client.get("/api/v1/admin/users")
    assert resp.status_code == 401
