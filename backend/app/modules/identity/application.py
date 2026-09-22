from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.security import (
    create_token,
    decode_token,
    token_digest,
    verify_password,
)
from backend.app.modules.identity.infrastructure import RefreshSession, User


class AuthenticationService:
    def __init__(self, db: Session):
        self.db = db

    def login(self, email: str, password: str) -> tuple[User, str, str]:
        user = self.db.scalar(select(User).where(User.email == email.lower()))
        if (
            not user
            or not user.is_active
            or not verify_password(password, user.password_hash)
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )
        return user, *self._issue_tokens(user)

    def refresh(self, refresh_token: str) -> tuple[User, str, str]:
        try:
            payload = decode_token(refresh_token)
        except Exception as exc:
            raise HTTPException(
                status_code=401, detail="Invalid refresh token"
            ) from exc
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        session = self.db.scalar(
            select(RefreshSession).where(RefreshSession.token_id == payload["jti"])
        )
        if (
            not session
            or session.revoked_at
            or session.token_hash != token_digest(refresh_token)
        ):
            raise HTTPException(
                status_code=401, detail="Refresh token is no longer active"
            )
        session.revoked_at = datetime.now(UTC)
        user = self.db.get(User, session.user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User is inactive")
        access_token, new_refresh_token = self._issue_tokens(user)
        self.db.commit()
        return user, access_token, new_refresh_token

    def logout(self, refresh_token: str) -> None:
        try:
            payload = decode_token(refresh_token)
        except Exception:
            return
        session = self.db.scalar(
            select(RefreshSession).where(RefreshSession.token_id == payload.get("jti"))
        )
        if session and not session.revoked_at:
            session.revoked_at = datetime.now(UTC)
            self.db.commit()

    def _issue_tokens(self, user: User) -> tuple[str, str]:
        settings = get_settings()
        access, _, _ = create_token(
            str(user.id), "access", timedelta(minutes=settings.access_token_minutes)
        )
        refresh, refresh_id, expires_at = create_token(
            str(user.id), "refresh", timedelta(days=settings.refresh_token_days)
        )
        self.db.add(
            RefreshSession(
                user_id=user.id,
                token_id=refresh_id,
                token_hash=token_digest(refresh),
                expires_at=expires_at,
            )
        )
        self.db.commit()
        return access, refresh
