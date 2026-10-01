from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.database import get_db
from backend.app.core.security import decode_token, token_digest
from backend.app.modules.identity.domain import Role
from backend.app.modules.identity.infrastructure import RTAuthSession, User

bearer = HTTPBearer(auto_error=False)


def current_session(
    session_token: str | None = Cookie(
        default=None,
        alias=get_settings().auth_cookie_name,
    ),
    db: Session = Depends(get_db),
) -> RTAuthSession:
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    session = db.scalar(
        select(RTAuthSession).where(
            RTAuthSession.session_token_hash == token_digest(session_token),
            RTAuthSession.revoked_at.is_(None),
        )
    )
    now = datetime.now(UTC)
    expires_at = session.expires_at if session else None
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    if not session or not expires_at or expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired",
        )
    return session


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    session_token: str | None = Cookie(
        default=None,
        alias=get_settings().auth_cookie_name,
    ),
    db: Session = Depends(get_db),
) -> User:
    if session_token:
        session = db.scalar(
            select(RTAuthSession).where(
                RTAuthSession.session_token_hash == token_digest(session_token),
                RTAuthSession.revoked_at.is_(None),
            )
        )
        now = datetime.now(UTC)
        expires_at = session.expires_at if session else None
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if session and expires_at and expires_at > now:
            user = db.get(User, session.user_id)
            if user and user.is_active and user.deleted_at is None:
                return user

    if get_settings().environment == "test" and credentials:
        try:
            payload = decode_token(credentials.credentials)
            if payload.get("type") != "access":
                raise ValueError
            user = db.get(User, UUID(payload["sub"]))
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token",
            ) from exc
        if user and user.is_active and user.deleted_at is None:
            return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )


def require_roles(*roles: Role) -> Callable:
    def role_check(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permission",
            )
        return user

    return role_check
