"""Step 8/9: registration, login, and the auth dependency."""


def test_register_happy_path(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"org_name": "Acme Co", "email": "alice@test.com", "password": "TestPass123!"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "alice@test.com"
    assert body["org_name"] == "Acme Co"
    assert body["role"] == "user"
    assert "hashed_password" not in body


def test_register_duplicate_email_conflicts(client):
    payload = {"org_name": "Acme Co", "email": "dupe@test.com", "password": "TestPass123!"}
    first = client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201

    second = client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409


def test_login_happy_path(client):
    client.post(
        "/api/v1/auth/register",
        json={"org_name": "Acme Co", "email": "bob@test.com", "password": "TestPass123!"},
    )
    resp = client.post("/api/v1/auth/login", data={"username": "bob@test.com", "password": "TestPass123!"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 20


def test_login_wrong_password_rejected(client):
    client.post(
        "/api/v1/auth/register",
        json={"org_name": "Acme Co", "email": "carol@test.com", "password": "TestPass123!"},
    )
    resp = client.post("/api/v1/auth/login", data={"username": "carol@test.com", "password": "WrongPassword!"})
    assert resp.status_code == 401


def test_me_requires_auth(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_me_returns_current_user(client, auth_headers):
    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "fixture_user@test.com"
