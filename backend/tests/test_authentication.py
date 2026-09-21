def login(client, email="admin@example.com", password="Password123!"):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def test_login_returns_tokens_and_user(client):
    response = login(client)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "administrator"
    assert body["access_token"]
    assert body["refresh_token"]


def test_invalid_password_is_rejected(client):
    assert login(client, password="WrongPassword!").status_code == 401


def test_protected_route_requires_access_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    access_token = login(client).json()["access_token"]
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "admin@example.com"


def test_role_permission_is_enforced_by_api(client):
    access_token = login(client, email="viewer@example.com").json()["access_token"]
    response = client.get("/api/v1/auth/admin-check", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 403


def test_refresh_rotates_token_and_logout_revokes_it(client):
    first = login(client).json()
    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert refreshed.status_code == 200
    second_refresh = refreshed.json()["refresh_token"]
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}).status_code == 401
    assert client.post("/api/v1/auth/logout", json={"refresh_token": second_refresh}).status_code == 204
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": second_refresh}).status_code == 401
