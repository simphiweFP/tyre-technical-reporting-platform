import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from sqlalchemy import select

from backend.app.core.config import get_settings
from backend.app.core.database import get_db
from backend.app.main import app
from backend.app.modules.identity import company_auth as auth
from backend.app.modules.identity.infrastructure import CompanySession, User
from backend.app.modules.reports.infrastructure import TechnicalReportRecord


@pytest.fixture
def company(client, monkeypatch):
    client.base_url = httpx.URL("https://testserver")
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "auth_issuer_url", "https://auth.internal")
    monkeypatch.setattr(settings, "public_app_url", "https://testserver")
    monkeypatch.setattr(
        settings,
        "auth_branch_scopes",
        {"PHX": {"company": "RTC", "warehouse": "RTCPHX"}},
    )
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    key["kid"] = "test-key"
    claims = {
        "iss": settings.auth_issuer_url,
        "aud": settings.auth_client_id,
        "sub": str(uuid4()),
        "iat": datetime.now(UTC).timestamp(),
        "exp": (datetime.now(UTC) + timedelta(minutes=10)).timestamp(),
        "typ": "id_token",
        "email": "company@example.com",
        "name": "Company User",
        "roles": ["administrator"],
        "companies": ["RTC"],
        "warehouses": {"RTC": ["RTCPHX"]},
    }
    calls = []

    def token(**overrides):
        return jwt.encode(
            {**claims, **overrides},
            private,
            algorithm="RS256",
            headers={"kid": "test-key"},
        )

    def provider(method, path, *, data=None):
        calls.append((method, path, data))
        if path.endswith("jwks.json"):
            return {"keys": [key]}
        if path == "/revoke":
            return {}
        return {"id_token": token(), "refresh_token": "provider-refresh-secret"}

    auth._jwks.clear()
    auth._jwks_until.clear()
    monkeypatch.setattr(auth, "provider_call", provider)
    return claims, calls, token


def sign_in(client):
    from urllib.parse import parse_qs, urlparse

    started = client.get("/api/v1/auth/company/login", follow_redirects=False)
    assert started.status_code == 307
    params = parse_qs(urlparse(started.headers["location"]).query)
    state = params["state"][0]
    result = client.get(
        "/api/auth/callback",
        params={"state": state, "code": "once-only-code"},
        follow_redirects=False,
    )
    assert result.status_code == 307, result.text
    return state, params, result


def test_company_login_pkce_cookie_session_and_logout(client, company):
    claims, calls, _ = company
    state, params, result = sign_in(client)
    assert params["client_id"] == ["RT-TechnicalClaim"]
    assert params["code_challenge_method"] == ["S256"]
    exchange = next(data for _, path, data in calls if path == "/token")
    challenge = (
        base64.urlsafe_b64encode(
            hashlib.sha256(exchange["code_verifier"].encode()).digest()
        )
        .rstrip(b"=")
        .decode()
    )
    assert challenge == params["code_challenge"][0]
    assert exchange["grant_type"] == "authorization_code"
    assert "provider-refresh-secret" not in result.text + result.headers[
        "location"
    ] + str(result.headers)
    assert "HttpOnly" in result.headers.get_list("set-cookie")[1]
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200 and me.json()["role"] == "administrator", me.text
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "Password123!"},
        ).status_code
        == 403
    )
    assert client.post("/api/v1/auth/company/logout").status_code == 403
    csrf = client.cookies.get(auth.CSRF_COOKIE)
    logged_out = client.post(
        "/api/v1/auth/company/logout", headers={"X-CSRF-Token": csrf}
    )
    assert logged_out.status_code == 204, logged_out.text
    assert calls[-1] == (
        "POST",
        "/revoke",
        {"refresh_token": "provider-refresh-secret"},
    )
    assert client.get("/api/v1/auth/me").status_code == 401
    assert (
        client.get(
            "/api/auth/callback", params={"state": state, "code": "once-only-code"}
        ).status_code
        == 401
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"aud": "rtportal"},
        {"iss": "https://other"},
        {"typ": "access_token"},
        {"exp": 1},
        {"roles": "administrator"},
        {"companies": ["OTHER"]},
        {"warehouses": {"RTC": "RTCPHX"}},
        {"sub": "not-a-uuid"},
    ],
)
def test_company_rejects_untrusted_claims(client, company, changes):
    with pytest.raises(HTTPException) as failure:
        auth.validate_identity(company[2](**changes))
    assert failure.value.status_code == 401


def test_company_wrong_state_and_local_registration_disabled(client, company):
    client.get("/api/v1/auth/company/login", follow_redirects=False)
    assert client.get("/api/auth/callback?state=wrong&code=test").status_code == 401
    assert (
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "new@example.com",
                "full_name": "New Person",
                "password": "Password12345!",
            },
        ).status_code
        == 403
    )


def test_company_jwks_rotation_refetches_once_and_rejects_hmac(client, company):
    issuer = get_settings().auth_issuer_url
    auth._jwks[issuer] = {"keys": [{"kid": "old-key"}]}
    auth._jwks_until[issuer] = float("inf")
    assert auth.validate_identity(company[2]())["sub"] == company[0]["sub"]
    assert len([call for call in company[1] if call[1].endswith("jwks.json")]) == 1
    invalid = jwt.encode(
        company[0], "untrusted-secret", algorithm="HS256", headers={"kid": "test-key"}
    )
    with pytest.raises(HTTPException) as failure:
        auth.validate_identity(invalid)
    assert failure.value.status_code == 401


def test_company_session_expiry_and_csrf_binding(client, company):
    sign_in(client)
    client.cookies.set(auth.CSRF_COOKIE, "forged", domain="testserver.local", path="/")
    assert (
        client.post(
            "/api/v1/auth/company/logout", headers={"X-CSRF-Token": "forged"}
        ).status_code
        == 403
    )
    with next(app.dependency_overrides[get_db]()) as db:
        session = db.scalar(select(CompanySession))
        session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401


def test_company_existing_user_requires_explicit_link(client, company, monkeypatch):
    claims, _, _ = company
    claims["email"] = "admin@example.com"
    client.get("/api/v1/auth/company/login", follow_redirects=False)
    state = client.cookies.get(auth.STATE_COOKIE)
    rejected = client.get(
        "/api/auth/callback",
        params={"state": state, "code": "code"},
        follow_redirects=False,
    )
    assert rejected.status_code == 409
    monkeypatch.setattr(
        get_settings(), "auth_user_links", {claims["sub"]: "admin@example.com"}
    )
    with next(app.dependency_overrides[get_db]()) as db:
        before = db.scalar(select(User).where(User.email == "admin@example.com")).id
    sign_in(client)
    assert client.get("/api/v1/auth/me").json()["id"] == str(before)


@pytest.mark.parametrize(
    "companies,warehouses,expected",
    [
        (["RTC"], {"RTC": ["RTCPHX"]}, 1),
        ([], {"RTC": ["RTCPHX"]}, 0),
        (["RTC"], {"RVS": ["RTCPHX"]}, 0),
        (["RTC"], {}, 0),
    ],
)
def test_company_branch_scoping_including_empty_grants(
    client, company, companies, warehouses, expected
):
    claims, _, _ = company
    claims.update(companies=companies, warehouses=warehouses)
    with next(app.dependency_overrides[get_db]()) as db:
        admin = db.scalar(select(User).where(User.email == "admin@example.com"))
        for branch, ref in [("PHX", "I000291"), ("OTHER", "I000292")]:
            db.add(
                TechnicalReportRecord(
                    claim_reference=ref,
                    branch_name=branch,
                    created_by=admin.id,
                    report_data={"claimReference": ref, "branch": branch},
                )
            )
        db.commit()
    sign_in(client)
    result = client.get("/api/v1/reports/records")
    assert result.status_code == 200, result.text
    assert len(result.json()["items"]) == expected
    assert client.get("/api/v1/auth/branches").status_code == 200


def test_company_refresh_and_encrypted_token_storage(client, company):
    sign_in(client)
    with next(app.dependency_overrides[get_db]()) as db:
        session = db.scalar(select(CompanySession))
        assert "provider-refresh-secret" not in session.refresh_ciphertext
        session.renewed_at = datetime.now(UTC) - timedelta(minutes=21)
        db.commit()
    assert client.get("/api/v1/auth/me").status_code == 200
    assert any(
        data and data.get("grant_type") == "refresh_token" for _, _, data in company[1]
    )


@pytest.mark.parametrize("status,expected", [(503, 200), (401, 401)])
def test_company_refresh_failure_handling(
    client, company, monkeypatch, status, expected
):
    sign_in(client)
    with next(app.dependency_overrides[get_db]()) as db:
        session = db.scalar(select(CompanySession))
        session.renewed_at = datetime.now(UTC) - timedelta(minutes=21)
        db.commit()
    attempted = []

    def unavailable(*args, **kwargs):
        attempted.append(True)
        raise HTTPException(status, "Provider unavailable")

    monkeypatch.setattr(auth, "provider_call", unavailable)
    assert client.get("/api/v1/auth/me").status_code == expected
    assert client.get("/api/v1/auth/me").status_code == expected
    assert len(attempted) == 1


def test_company_scopes_claims_deliveries_audit_and_writes(client, company):
    from backend.app.modules.auditing.infrastructure import AuditEvent
    from backend.app.modules.claims.infrastructure import ClaimCase
    from backend.app.modules.delivery.infrastructure import DeliveryAttempt

    with next(app.dependency_overrides[get_db]()) as db:
        admin = db.scalar(select(User).where(User.email == "admin@example.com"))
        hidden = None
        for branch, reference in [("PHX", "I000291"), ("OTHER", "I000292")]:
            report = TechnicalReportRecord(
                claim_reference=reference,
                branch_name=branch,
                created_by=admin.id,
                report_data={"claimReference": reference, "branch": branch},
            )
            db.add(report)
            db.flush()
            db.add(
                ClaimCase(
                    report_id=report.id,
                    assigned_to=admin.id,
                    handed_over_by=admin.id,
                    data={
                        "claim_date": "2026-09-01",
                        "supplier_status": "Under review",
                    },
                )
            )
            db.add(
                DeliveryAttempt(
                    claim_reference=reference,
                    recipient_email="recipient@example.com",
                    requested_by=admin.id,
                    report_payload={"claimReference": reference},
                    status="Sent",
                )
            )
            db.add(
                AuditEvent(
                    actor_id=admin.id,
                    action="report.saved",
                    entity_type="technical_report",
                    entity_id=reference,
                    details={},
                )
            )
            if branch == "OTHER":
                hidden = str(report.id)
        db.commit()
    sign_in(client)
    assert client.get(f"/api/v1/reports/records/{hidden}").status_code == 404
    claims = client.get("/api/v1/claims")
    assert claims.status_code == 200, claims.text
    assert len(claims.json()["items"]) == 1
    assert claims.json()["items"][0]["claim_reference"] == "I000291"
    deliveries = client.get("/api/v1/deliveries")
    assert deliveries.status_code == 200, deliveries.text
    assert len(deliveries.json()["items"]) == 1
    assert deliveries.json()["items"][0]["claim_reference"] == "I000291"
    audit = client.get("/api/v1/admin/audit-events")
    assert audit.status_code == 200, audit.text
    assert all(item["entity_id"] != "I000292" for item in audit.json()["items"])
    csrf = client.cookies.get(auth.CSRF_COOKIE)
    saved = client.put(
        f"/api/v1/reports/records/{uuid4()}",
        headers={"X-CSRF-Token": csrf},
        json={
            "report": {
                "claimReference": "I000293",
                "status": "Draft",
                "branch": "OTHER",
            }
        },
    )
    assert saved.status_code == 403, saved.text
