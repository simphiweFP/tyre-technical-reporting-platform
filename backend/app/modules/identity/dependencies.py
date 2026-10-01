from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.database import get_db
from backend.app.core.security import token_digest
from backend.app.modules.identity.domain import Role
from backend.app.modules.identity.infrastructure import RTAuthSession, User


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
    session: RTAuthSession = Depends(current_session),
    db: Session = Depends(get_db),
) -> User:
    user = db.get(User, session.user_id)
    if not user or not user.is_active or user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is inactive",
        )
    return user


def require_roles(*roles: Role) -> Callable:
    def role_check(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permission",
            )
        return user

    return role_check
