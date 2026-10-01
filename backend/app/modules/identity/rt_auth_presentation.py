import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.database import get_db
from backend.app.core.security import hash_password, token_digest
from backend.app.modules.auditing.infrastructure import AuditEvent
from backend.app.modules.identity.domain import Role
from backend.app.modules.identity.infrastructure import RTAuthSession, User
from backend.app.modules.identity.rt_auth import RTAuthClient, RTAuthError

router = APIRouter(prefix="/auth", tags=["Royal Tyres authentication"])


def _role_from_claims(role_codes: list[str]) -> Role:
    normalized = {
        str(role).strip().lower().replace("-", "_").replace(" ", "_")
        for role in role_codes
    }
    for role in (Role.ADMINISTRATOR, Role.REPORT_CAPTURER, Role.VIEWER):
        if role.value in normalized:
            return role
    return Role.PENDING


def _settings():
    settings = get_settings()
    if not (
        settings.auth_issuer_url
        and settings.auth_client_id
        and settings.auth_client_secret
        and settings.auth_redirect_uri
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Royal Tyres RT-Auth is not configured.",
        )
    return settings


@router.get("/company-login")
def company_login(request: Request):
    settings = _settings()
    state = secrets.token_urlsafe(32)
    verifier = RTAuthClient.pkce_verifier()
    request.session["rt_auth_login"] = {
        "state": state,
        "verifier": verifier,
    }
    return RedirectResponse(
        RTAuthClient(settings).authorize_url(state, verifier),
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/callback")
def company_callback(
    request: Request,
    code: str,
    state: str,
    db: Session = Depends(get_db),
):
    settings = _settings()
    pending = request.session.pop("rt_auth_login", None)
    if not pending or not secrets.compare_digest(
        str(pending.get("state") or ""),
        state,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid authentication state.",
        )

    client = RTAuthClient(settings)
    try:
        tokens = client.exchange_code(code, str(pending.get("verifier") or ""))
        claims = client.validate_id_token(str(tokens["id_token"]))
    except RTAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    subject = str(claims["sub"])
    email = str(claims["email"]).strip().lower()
    full_name = str(claims.get("name") or claims.get("username") or email)
    roles = [str(value) for value in (claims.get("roles") or [])]
    companies = [str(value) for value in (claims.get("companies") or [])]
    warehouses = dict(claims.get("warehouses") or {})

    user = db.scalar(
        select(User).where(
            User.external_provider == "rt_auth",
            User.external_subject == subject,
        )
    )
    if not user:
        user = db.scalar(select(User).where(User.email == email))

    if not user:
        user = User(
            email=email,
            full_name=full_name,
            password_hash=hash_password(secrets.token_urlsafe(48)),
            role=_role_from_claims(roles),
            branch_id=None,
            is_active=True,
            external_provider="rt_auth",
            external_subject=subject,
        )
        db.add(user)
        db.flush()
        audit_action = "user.rt_auth_provisioned"
    else:
        user.email = email
        user.full_name = full_name
        user.role = _role_from_claims(roles)
        user.is_active = True
        user.deleted_at = None
        user.external_provider = "rt_auth"
        user.external_subject = subject
        audit_action = "user.rt_auth_signed_in"

    session_token = secrets.token_urlsafe(48)
    csrf_token = secrets.token_urlsafe(32)
    app_session = RTAuthSession(
        user_id=user.id,
        session_token_hash=token_digest(session_token),
        csrf_token_hash=token_digest(csrf_token),
        refresh_token=str(tokens["refresh_token"]),
        roles=roles,
        companies=companies,
        warehouses=warehouses,
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC)
        + timedelta(hours=settings.auth_session_hours),
    )
    db.add(app_session)
    db.add(
        AuditEvent(
            actor_id=user.id,
            action=audit_action,
            entity_type="user",
            entity_id=str(user.id),
            details={
                "provider": "rt_auth",
                "roles": roles,
                "companies": companies,
            },
        )
    )
    db.commit()

    response = RedirectResponse(
        f"{settings.public_app_url.rstrip('/')}/dashboard",
        status_code=status.HTTP_302_FOUND,
    )
    response.set_cookie(
        settings.auth_cookie_name,
        session_token,
        max_age=settings.auth_session_hours * 3600,
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        settings.auth_csrf_cookie_name,
        csrf_token,
        max_age=settings.auth_session_hours * 3600,
        httponly=False,
        secure=settings.environment == "production",
        samesite="lax",
        path="/",
    )
    return response


@router.post("/company-logout", status_code=status.HTTP_204_NO_CONTENT)
def company_logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    settings = get_settings()
    raw = request.cookies.get(settings.auth_cookie_name)
    if raw:
        session = db.scalar(
            select(RTAuthSession).where(
                RTAuthSession.session_token_hash == token_digest(raw),
                RTAuthSession.revoked_at.is_(None),
            )
        )
        if session:
            try:
                RTAuthClient(settings).revoke(session.refresh_token)
            except RTAuthError:
                pass
            session.revoked_at = datetime.now(UTC)
            db.commit()

    response.delete_cookie(settings.auth_cookie_name, path="/")
    response.delete_cookie(settings.auth_csrf_cookie_name, path="/")
