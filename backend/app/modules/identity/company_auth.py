"""RT-Auth's custom authorization-code flow; provider tokens stay server-side."""

import base64
import hashlib
import secrets
import ssl
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from uuid import UUID

import httpx
import jwt
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from pydantic import EmailStr, TypeAdapter
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.database import get_db
from backend.app.core.security import hash_password, token_digest
from backend.app.modules.identity.domain import Role
from backend.app.modules.identity.infrastructure import (
    CompanyLogin,
    CompanySession,
    User,
)

router = APIRouter(tags=["Company authentication"])
SESSION_COOKIE = "rt_claim_session"
CSRF_COOKIE = "rt_claim_csrf"
STATE_COOKIE = "rt_claim_login"
_jwks: dict = {}
_jwks_until: dict = {}


def enabled():
    if not get_settings().auth_enabled:
        raise HTTPException(404, "Company sign-in is not enabled")


def cipher():
    digest = hashlib.sha256(get_settings().jwt_secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def refresh_secret(session):
    try:
        return cipher().decrypt(session.refresh_ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise HTTPException(401, "Company session expired; sign in again") from exc


def provider_call(method, path, *, data=None):
    settings = get_settings()
    try:
        context = ssl.create_default_context(cafile=settings.auth_ca_file)
        with httpx.Client(
            verify=context, timeout=settings.auth_timeout_seconds
        ) as client:
            response = client.request(
                method,
                settings.auth_issuer_url.rstrip("/") + path,
                data=data,
                auth=httpx.BasicAuth(
                    settings.auth_client_id, settings.auth_client_secret
                )
                if method == "POST"
                else None,
            )
        if response.status_code in (400, 401, 403):
            raise HTTPException(401, "Company sign-in is no longer valid")
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, OSError, ValueError) as exc:
        raise HTTPException(503, "Company sign-in is temporarily unavailable") from exc


def validate_identity(token):
    settings = get_settings()
    issuer = settings.auth_issuer_url
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256" or not header.get("kid"):
            raise ValueError("Invalid token header")
        if time.monotonic() >= _jwks_until.get(issuer, 0):
            _jwks[issuer] = provider_call("GET", "/.well-known/jwks.json")
            _jwks_until[issuer] = time.monotonic() + 3600
        key = next(
            (k for k in _jwks[issuer]["keys"] if k.get("kid") == header["kid"]), None
        )
        if key is None:
            _jwks[issuer] = provider_call("GET", "/.well-known/jwks.json")
            key = next(
                (k for k in _jwks[issuer]["keys"] if k.get("kid") == header["kid"]),
                None,
            )
        if not key or key.get("kty") != "RSA":
            raise ValueError("Unknown signing key")
        claims = jwt.decode(
            token,
            jwt.PyJWK.from_dict(key, algorithm="RS256").key,
            algorithms=["RS256"],
            audience=settings.auth_client_id,
            issuer=issuer,
            leeway=5,
            options={
                "require": [
                    "iss",
                    "sub",
                    "aud",
                    "exp",
                    "iat",
                    "typ",
                    "email",
                    "roles",
                    "companies",
                    "warehouses",
                ]
            },
        )
        if claims["typ"] != "id_token":
            raise ValueError("Wrong token type")
        if claims["aud"] != settings.auth_client_id:
            raise ValueError("Wrong audience")
        UUID(claims["sub"])
        TypeAdapter(EmailStr).validate_python(claims["email"])
        if not isinstance(claims["roles"], list) or not all(
            isinstance(r, str) for r in claims["roles"]
        ):
            raise ValueError("Invalid roles")
        if not isinstance(claims["companies"], list) or not all(
            c in {"RTC", "RVS"} for c in claims["companies"]
        ):
            raise ValueError("Invalid companies")
        if not isinstance(claims["warehouses"], dict) or not all(
            c in {"RTC", "RVS"}
            and isinstance(ws, list)
            and all(isinstance(w, str) for w in ws)
            for c, ws in claims["warehouses"].items()
        ):
            raise ValueError("Invalid warehouses")
        return claims
    except (jwt.PyJWTError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(401, "Company identity could not be verified") from exc


def local_profile(db, claims):
    subject, email = claims["sub"], claims["email"].lower()
    user = db.scalar(
        select(User).where(
            User.external_provider == "rt-auth", User.external_subject == subject
        )
    )
    if not user:
        existing = db.scalar(select(User).where(User.email == email))
        linked_email = get_settings().auth_user_links.get(subject, "").lower()
        if existing:
            if (
                linked_email != existing.email.lower()
                or existing.external_provider not in (None, "rt-auth")
                or (existing.external_subject and existing.external_subject != subject)
            ):
                raise HTTPException(
                    409,
                    "Ask an administrator to link this company identity "
                    "to the existing local account",
                )
            user = existing
        else:
            user = User(
                email=email,
                full_name=claims.get("name") or email,
                password_hash=hash_password(secrets.token_urlsafe(40)),
                role=Role.PENDING,
                is_active=True,
            )
            db.add(user)
        user.external_provider, user.external_subject = "rt-auth", subject
    if not user.is_active or user.deleted_at:
        raise HTTPException(403, "User account is inactive")
    user.role = next(
        (
            r
            for r in [
                Role.ADMINISTRATOR,
                Role.CLAIMS_ADMINISTRATOR,
                Role.REPORT_CAPTURER,
                Role.VIEWER,
            ]
            if r.value in claims["roles"]
        ),
        Role.PENDING,
    )
    user.full_name = claims.get("name") or user.full_name
    db.flush()
    return user


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


@router.get("/api/v1/auth/config")
def auth_config():
    return {"provider": "rt-auth" if get_settings().auth_enabled else "local"}


@router.get("/api/v1/auth/company/login")
def login(db: Session = Depends(get_db)):
    enabled()
    settings = get_settings()
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    db.add(
        CompanyLogin(
            state_hash=token_digest(state),
            verifier=verifier,
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
    )
    db.commit()
    url = (
        settings.auth_issuer_url.rstrip("/")
        + "/authorize?"
        + urlencode(
            {
                "client_id": settings.auth_client_id,
                "redirect_uri": settings.auth_redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
    )
    response = RedirectResponse(url)
    response.set_cookie(
        STATE_COOKIE,
        state,
        secure=True,
        httponly=True,
        samesite="lax",
        path="/api",
        max_age=600,
    )
    return response


@router.get("/api/auth/callback")
def callback(request: Request, db: Session = Depends(get_db)):
    enabled()
    state = request.query_params.get("state", "")
    if not state or not secrets.compare_digest(
        state, request.cookies.get(STATE_COOKIE, "")
    ):
        raise HTTPException(401, "Company login state did not match")
    transaction = db.get(CompanyLogin, token_digest(state), with_for_update=True)
    if not transaction or utc(transaction.expires_at) <= datetime.now(UTC):
        raise HTTPException(401, "Company login expired; sign in again")
    verifier = transaction.verifier
    db.delete(transaction)
    db.commit()
    if request.query_params.get("error") or not request.query_params.get("code"):
        raise HTTPException(401, "Company sign-in was cancelled")
    tokens = provider_call(
        "POST",
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": request.query_params["code"],
            "redirect_uri": get_settings().auth_redirect_uri,
            "code_verifier": verifier,
        },
    )
    claims = validate_identity(tokens.get("id_token", ""))
    if not isinstance(tokens.get("refresh_token"), str) or not tokens["refresh_token"]:
        raise HTTPException(401, "Company sign-in did not provide a session")
    user = local_profile(db, claims)
    session_token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    db.add(
        CompanySession(
            token_hash=token_digest(session_token),
            user_id=user.id,
            csrf_hash=token_digest(csrf),
            refresh_ciphertext=cipher()
            .encrypt(tokens["refresh_token"].encode())
            .decode(),
            claims=claims,
            renewed_at=now,
            expires_at=now + timedelta(hours=8),
        )
    )
    db.commit()
    response = RedirectResponse(
        get_settings().public_app_url.rstrip("/") + "/auth/callback?provider=rt-auth"
    )
    response.delete_cookie(STATE_COOKIE, path="/api")
    response.set_cookie(
        SESSION_COOKIE,
        session_token,
        secure=True,
        httponly=True,
        samesite="lax",
        path="/api",
        max_age=28800,
    )
    response.set_cookie(
        CSRF_COOKIE, csrf, secure=True, samesite="lax", path="/", max_age=28800
    )
    return response


def company_user(request, db):
    enabled()
    session_token = request.cookies.get(SESSION_COOKIE)
    session = (
        db.get(CompanySession, token_digest(session_token)) if session_token else None
    )
    if not session or utc(session.expires_at) <= datetime.now(UTC):
        raise HTTPException(401, "Company session expired; sign in again")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf = request.cookies.get(CSRF_COOKIE, "")
        if (
            not csrf
            or not secrets.compare_digest(csrf, request.headers.get("x-csrf-token", ""))
            or not secrets.compare_digest(token_digest(csrf), session.csrf_hash)
        ):
            raise HTTPException(403, "Session request could not be verified")
    if datetime.now(UTC) - utc(session.renewed_at) >= timedelta(minutes=20):
        session = db.scalar(
            select(CompanySession)
            .where(CompanySession.token_hash == session.token_hash)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if datetime.now(UTC) - utc(session.renewed_at) >= timedelta(minutes=20):
            try:
                tokens = provider_call(
                    "POST",
                    "/token",
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_secret(session),
                    },
                )
                claims = validate_identity(tokens.get("id_token", ""))
                if claims["sub"] != session.claims["sub"] or not tokens.get(
                    "refresh_token"
                ):
                    raise HTTPException(401, "Company session identity changed")
                user = local_profile(db, claims)
                if user.id != session.user_id:
                    raise HTTPException(401, "Company session identity changed")
                session.claims = claims
                session.refresh_ciphertext = (
                    cipher().encrypt(tokens["refresh_token"].encode()).decode()
                )
                session.renewed_at = datetime.now(UTC)
            except HTTPException as exc:
                if exc.status_code != 503:
                    db.delete(session)
                    db.commit()
                    raise
                # Throttle temporary failures too; do not call RT-Auth every request.
                session.renewed_at = datetime.now(UTC)
            db.commit()
    user = db.get(User, session.user_id)
    if not user or not user.is_active or user.deleted_at:
        raise HTTPException(401, "User account is inactive")
    from backend.app.modules.identity.company_scope import apply_scope

    apply_scope(db, session.claims)
    db.info["company_user_id"] = user.id
    user.role = next(
        (
            r
            for r in [
                Role.ADMINISTRATOR,
                Role.CLAIMS_ADMINISTRATOR,
                Role.REPORT_CAPTURER,
                Role.VIEWER,
            ]
            if r.value in session.claims["roles"]
        ),
        Role.PENDING,
    )
    ids = db.info["company_branch_ids"]
    if user.branch_id not in ids:
        user.branch_id = ids[0] if ids else None
    return user


@router.post("/api/v1/auth/company/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    company_user(request, db)
    session = db.get(CompanySession, token_digest(request.cookies[SESSION_COOKIE]))
    refresh = refresh_secret(session)
    db.delete(session)
    db.commit()
    try:
        provider_call("POST", "/revoke", data={"refresh_token": refresh})
    except HTTPException:
        # Local logout always completes even when RT-Auth cannot be reached.
        pass
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, path="/api")
    response.delete_cookie(CSRF_COOKIE, path="/")
    return response
