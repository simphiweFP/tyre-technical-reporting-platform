from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base
from backend.app.modules.identity.domain import Role


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index(
            "uq_users_rt_auth_subject",
            "external_subject",
            unique=True,
            sqlite_where=text("external_provider = 'rt-auth'"),
            postgresql_where=text("external_provider = 'rt-auth'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(150))
    job_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(40), default=Role.VIEWER)
    branch_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("branches.id"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    external_provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    external_subject: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )


class RefreshSession(Base):
    __tablename__ = "refresh_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    token_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class CompanyLogin(Base):
    __tablename__ = "company_auth_logins"
    state_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    verifier: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CompanySession(Base):
    __tablename__ = "company_auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    refresh_ciphertext: Mapped[str] = mapped_column(Text)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    claims: Mapped[dict] = mapped_column(JSON)
    renewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
