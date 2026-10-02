import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from backend.app import seed as seed_module
from backend.app.core.config import Settings
from backend.app.core.database import get_db
from backend.app.core.security import verify_password
from backend.app.main import app
from backend.app.modules.identity.domain import Role
from backend.app.modules.identity.infrastructure import User


def configure_seed(monkeypatch, settings):
    with next(app.dependency_overrides[get_db]()) as db:
        factory = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
    monkeypatch.setattr(seed_module, "SessionLocal", factory)
    monkeypatch.setattr(seed_module, "get_settings", lambda: settings)
    return factory


def test_seed_claims_admin_login_and_preserve_existing_password(client, monkeypatch):
    settings = Settings(
        environment="test",
        seed_admin_email="admin@example.com",
        seed_admin_password="Password123!",
        seed_claims_admin_email="CLAIMS@royaltyres.co.za",
        seed_claims_admin_password="ClaimsPass123!",
    )
    factory = configure_seed(monkeypatch, settings)
    seed_module.seed()
    with factory() as db:
        user = db.scalar(select(User).where(User.email == "claims@royaltyres.co.za"))
        first_id = user.id
        assert user.role == Role.CLAIMS_ADMINISTRATOR
        assert user.is_active and user.branch_id
        assert verify_password("ClaimsPass123!", user.password_hash)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "claims@royaltyres.co.za", "password": "ClaimsPass123!"},
    )
    assert response.status_code == 200
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    assert client.get("/api/v1/claims", headers=headers).status_code == 200
    assert client.get("/api/v1/auth/users", headers=headers).status_code == 403
    settings.seed_claims_admin_password = "DifferentPassword123!"
    seed_module.seed()
    with factory() as db:
        users = db.scalars(
            select(User).where(User.email == "claims@royaltyres.co.za")
        ).all()
        assert len(users) == 1 and users[0].id == first_id
        assert verify_password("ClaimsPass123!", users[0].password_hash)


def test_claims_seed_uses_configured_admin_password_when_blank(client, monkeypatch):
    settings = Settings(
        environment="test",
        seed_admin_email="admin@example.com",
        seed_admin_password="ConfiguredPassword123!",
        seed_claims_admin_email="claims@royaltyres.co.za",
        seed_claims_admin_password="",
    )
    factory = configure_seed(monkeypatch, settings)
    seed_module.seed()
    with factory() as db:
        user = db.scalar(select(User).where(User.email == "claims@royaltyres.co.za"))
        assert verify_password("ConfiguredPassword123!", user.password_hash)
        admin = db.scalar(select(User).where(User.email == "admin@example.com"))
        assert verify_password("Password123!", admin.password_hash)


def test_seed_never_promotes_existing_user_or_duplicates_admin(client, monkeypatch):
    settings = Settings(
        environment="test",
        seed_admin_email="admin@example.com",
        seed_claims_admin_email="viewer@example.com",
    )
    factory = configure_seed(monkeypatch, settings)
    with pytest.raises(RuntimeError, match="belongs to another role"):
        seed_module.seed()
    with factory() as db:
        assert (
            db.scalar(select(User).where(User.email == "viewer@example.com")).role
            == Role.VIEWER
        )
    settings.seed_claims_admin_email = "admin@example.com"
    with pytest.raises(RuntimeError, match="separate email"):
        seed_module.seed()
