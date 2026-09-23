import pytest

from backend.app.core.config import Settings


def test_production_configuration_rejects_unsafe_defaults():
    settings = Settings(
        environment="production",
        database_url="sqlite:///production.db",
        allowed_origins="http://localhost:4200",
        public_app_url="http://localhost:4200",
    )

    with pytest.raises(RuntimeError, match="Unsafe production configuration"):
        settings.validate_for_startup()


def test_request_responses_include_correlation_and_security_headers(client):
    response = client.get("/health", headers={"X-Request-ID": "quality-test-123"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "quality-test-123"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_root_redirects_to_swagger(client):
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/docs"


def test_swagger_security_policy_allows_required_assets(client):
    response = client.get("/docs")

    assert response.status_code == 200
    policy = response.headers["Content-Security-Policy"]
    assert "script-src https://cdn.jsdelivr.net" in policy
    assert "style-src https://cdn.jsdelivr.net 'unsafe-inline'" in policy
    assert "connect-src 'self'" in policy
