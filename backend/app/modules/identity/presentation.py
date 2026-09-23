import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from uuid import UUID

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.database import get_db
from backend.app.core.security import hash_password, token_digest
from backend.app.modules.auditing.infrastructure import AuditEvent
from backend.app.modules.branches.infrastructure import Branch
from backend.app.modules.delivery.domain import EmailMessage
from backend.app.modules.delivery.infrastructure import SmtpEmailGateway
from backend.app.modules.identity.application import AuthenticationService
from backend.app.modules.identity.dependencies import current_user, require_roles
from backend.app.modules.identity.domain import Role
from backend.app.modules.identity.infrastructure import (
    PasswordResetToken,
    RefreshSession,
    User,
)
from backend.app.modules.identity.schemas import (
    BranchCreateRequest,
    BranchResponse,
    BranchUpdateRequest,
    LoginRequest,
    LogoutRequest,
    ManagedUserResponse,
    PasswordForgotRequest,
    PasswordResetRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserCreateRequest,
    UserCreateResponse,
    UserResponse,
    UserUpdateRequest,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
oauth = OAuth()


def _microsoft_client():
    settings = get_settings()
    if not settings.microsoft_client_id or not settings.microsoft_client_secret:
        raise HTTPException(
            status_code=503, detail="Microsoft sign-in is not configured"
        )
    client = oauth.create_client("microsoft")
    if client:
        return client
    return oauth.register(
        name="microsoft",
        client_id=settings.microsoft_client_id,
        client_secret=settings.microsoft_client_secret,
        server_metadata_url=f"https://login.microsoftonline.com/{settings.microsoft_tenant_id}/v2.0/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    email = str(request.email).lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(
            status_code=409, detail="An account with this email already exists"
        )
    user = User(
        email=email,
        full_name=request.full_name.strip(),
        password_hash=hash_password(request.password),
        role=Role.PENDING,
        branch_id=None,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(
        AuditEvent(
            actor_id=user.id,
            action="user.self_registered",
            entity_type="user",
            entity_id=str(user.id),
            details={"provider": "password"},
        )
    )
    db.commit()
    user, access_token, refresh_token = AuthenticationService(db).login(
        email, request.password
    )
    return TokenResponse(
        access_token=access_token, refresh_token=refresh_token, user=user
    )


@router.get("/microsoft/login")
async def microsoft_login(request: Request):
    return await _microsoft_client().authorize_redirect(
        request, get_settings().microsoft_redirect_uri
    )


@router.get("/microsoft/callback")
async def microsoft_callback(request: Request, db: Session = Depends(get_db)):
    try:
        token = await _microsoft_client().authorize_access_token(request)
        identity = token.get("userinfo") or await _microsoft_client().userinfo(
            token=token
        )
    except OAuthError as exc:
        raise HTTPException(status_code=401, detail="Microsoft sign-in failed") from exc
    email = str(
        identity.get("email") or identity.get("preferred_username") or ""
    ).lower()
    subject = str(identity.get("sub") or "")
    if not email or not subject:
        raise HTTPException(
            status_code=401, detail="Microsoft account did not provide an email"
        )
    user = db.scalar(
        select(User).where(
            User.external_provider == "microsoft", User.external_subject == subject
        )
    )
    if not user:
        user = db.scalar(select(User).where(User.email == email))
    if not user:
        user = User(
            email=email,
            full_name=str(identity.get("name") or email.split("@")[0]),
            password_hash=hash_password(secrets.token_urlsafe(40)),
            role=Role.PENDING,
            is_active=True,
            external_provider="microsoft",
            external_subject=subject,
        )
        db.add(user)
        db.flush()
        db.add(
            AuditEvent(
                actor_id=user.id,
                action="user.self_registered",
                entity_type="user",
                entity_id=str(user.id),
                details={"provider": "microsoft"},
            )
        )
        db.commit()
    elif user.external_provider and user.external_subject != subject:
        raise HTTPException(
            status_code=409,
            detail="This email is linked to a different Microsoft identity",
        )
    elif not user.external_provider:
        user.external_provider = "microsoft"
        user.external_subject = subject
        db.commit()
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is inactive")
    access, refresh = AuthenticationService(db)._issue_tokens(user)
    fragment = urlencode({"access_token": access, "refresh_token": refresh})
    return RedirectResponse(f"{get_settings().public_app_url}/auth/callback#{fragment}")


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user, access_token, refresh_token = AuthenticationService(db).login(
        request.email, request.password
    )
    return TokenResponse(
        access_token=access_token, refresh_token=refresh_token, user=user
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(request: RefreshRequest, db: Session = Depends(get_db)):
    user, access_token, refresh_token = AuthenticationService(db).refresh(
        request.refresh_token
    )
    return TokenResponse(
        access_token=access_token, refresh_token=refresh_token, user=user
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: LogoutRequest, db: Session = Depends(get_db)):
    AuthenticationService(db).logout(request.refresh_token)


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(current_user)):
    return user


@router.get("/admin-check", response_model=UserResponse)
def admin_check(user: User = Depends(require_roles(Role.ADMINISTRATOR))):
    return user


@router.get("/branches", response_model=list[BranchResponse])
def branches(
    db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMINISTRATOR))
):
    return db.scalars(select(Branch).order_by(Branch.name)).all()


@router.post(
    "/branches", response_model=BranchResponse, status_code=status.HTTP_201_CREATED
)
def create_branch(
    request: BranchCreateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(Role.ADMINISTRATOR)),
):
    code = request.code.strip().upper()
    if db.scalar(select(Branch).where(Branch.code == code)):
        raise HTTPException(status_code=409, detail="Branch code already exists")
    branch = Branch(
        code=code,
        name=request.name.strip(),
        routing_email=str(request.routing_email or "").lower(),
    )
    db.add(branch)
    db.flush()
    db.add(
        AuditEvent(
            actor_id=actor.id,
            action="branch.created",
            entity_type="branch",
            entity_id=str(branch.id),
            details={"code": code},
        )
    )
    db.commit()
    db.refresh(branch)
    return branch


@router.patch("/branches/{branch_id}", response_model=BranchResponse)
def update_branch(
    branch_id: UUID,
    request: BranchUpdateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(Role.ADMINISTRATOR)),
):
    branch = db.get(Branch, branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    changes = request.model_dump(exclude_unset=True)
    if "routing_email" in changes:
        changes["routing_email"] = str(changes["routing_email"] or "").lower()
    if "code" in changes:
        changes["code"] = changes["code"].strip().upper()
        duplicate = db.scalar(
            select(Branch).where(Branch.code == changes["code"], Branch.id != branch.id)
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="Branch code already exists")
    for field, value in changes.items():
        setattr(branch, field, value)
    db.add(
        AuditEvent(
            actor_id=actor.id,
            action="branch.updated",
            entity_type="branch",
            entity_id=str(branch.id),
            details={"fields": sorted(changes)},
        )
    )
    db.commit()
    db.refresh(branch)
    return branch


@router.get("/users", response_model=list[ManagedUserResponse])
def users(
    db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMINISTRATOR))
):
    return db.scalars(select(User).order_by(User.full_name)).all()


@router.post(
    "/users", response_model=UserCreateResponse, status_code=status.HTTP_201_CREATED
)
def create_user(
    request: UserCreateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(Role.ADMINISTRATOR)),
):
    if request.role not in {role.value for role in Role}:
        raise HTTPException(status_code=422, detail="Invalid role")
    if db.scalar(select(User).where(User.email == str(request.email).lower())):
        raise HTTPException(status_code=409, detail="Email already exists")
    if request.branch_id and not db.get(Branch, request.branch_id):
        raise HTTPException(status_code=422, detail="Branch not found")
    temporary_password = secrets.token_urlsafe(12) + "A1!"
    user = User(
        email=str(request.email).lower(),
        full_name=request.full_name.strip(),
        job_title=request.job_title,
        password_hash=hash_password(temporary_password),
        role=request.role,
        branch_id=request.branch_id,
    )
    db.add(user)
    db.flush()
    db.add(
        AuditEvent(
            actor_id=actor.id,
            action="user.created",
            entity_type="user",
            entity_id=str(user.id),
            details={"email": user.email, "role": user.role},
        )
    )
    db.commit()
    db.refresh(user)
    return UserCreateResponse(
        **ManagedUserResponse.model_validate(user).model_dump(),
        temporary_password=temporary_password,
    )


@router.patch("/users/{user_id}", response_model=ManagedUserResponse)
def update_user(
    user_id: UUID,
    request: UserUpdateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(Role.ADMINISTRATOR)),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    changes = request.model_dump(exclude_unset=True)
    if "role" in changes and changes["role"] not in {role.value for role in Role}:
        raise HTTPException(status_code=422, detail="Invalid role")
    if user.id == actor.id and changes.get("is_active") is False:
        raise HTTPException(
            status_code=409, detail="You cannot deactivate your own account"
        )
    for field, value in changes.items():
        setattr(user, field, value)
    if changes.get("is_active") is False:
        _revoke_sessions(user.id, db)
    db.add(
        AuditEvent(
            actor_id=actor.id,
            action="user.updated",
            entity_type="user",
            entity_id=str(user.id),
            details={"fields": sorted(changes)},
        )
    )
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{user_id}/reset-password")
def admin_reset_password(
    user_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(Role.ADMINISTRATOR)),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    temporary_password = secrets.token_urlsafe(12) + "A1!"
    user.password_hash = hash_password(temporary_password)
    _revoke_sessions(user.id, db)
    db.add(
        AuditEvent(
            actor_id=actor.id,
            action="user.password_reset",
            entity_type="user",
            entity_id=str(user.id),
            details={},
        )
    )
    db.commit()
    return {"temporary_password": temporary_password}


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(
    request: PasswordForgotRequest,
    tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    user = db.scalar(
        select(User).where(
            User.email == str(request.email).lower(), User.is_active.is_(True)
        )
    )
    if user:
        token = secrets.token_urlsafe(40)
        settings = get_settings()
        db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=token_digest(token),
                expires_at=datetime.now(UTC)
                + timedelta(minutes=settings.password_reset_minutes),
            )
        )
        db.add(
            AuditEvent(
                actor_id=user.id,
                action="user.password_reset_requested",
                entity_type="user",
                entity_id=str(user.id),
                details={},
            )
        )
        db.commit()
        link = f"{settings.public_app_url}/reset-password?token={token}"
        tasks.add_task(
            SmtpEmailGateway(settings).send,
            EmailMessage(
                subject="Reset your Royal Tyres password",
                body=(
                    f"Use this link within {settings.password_reset_minutes} "
                    f"minutes:\n{link}"
                ),
                to=(user.email,),
                cc=(),
            ),
        )
    return {"message": "If the account exists, reset instructions have been sent"}


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(request: PasswordResetRequest, db: Session = Depends(get_db)):
    reset = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_digest(request.token),
            PasswordResetToken.used_at.is_(None),
        )
    )
    expires_at = (
        reset.expires_at.replace(tzinfo=UTC)
        if reset and reset.expires_at.tzinfo is None
        else (reset.expires_at if reset else None)
    )
    if not reset or not expires_at or expires_at < datetime.now(UTC):
        raise HTTPException(status_code=400, detail="Reset token is invalid or expired")
    user = db.get(User, reset.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="Reset token is invalid or expired")
    user.password_hash = hash_password(request.new_password)
    reset.used_at = datetime.now(UTC)
    _revoke_sessions(user.id, db)
    db.add(
        AuditEvent(
            actor_id=user.id,
            action="user.password_reset_completed",
            entity_type="user",
            entity_id=str(user.id),
            details={},
        )
    )
    db.commit()


def _revoke_sessions(user_id: UUID, db: Session) -> None:
    for session in db.scalars(
        select(RefreshSession).where(
            RefreshSession.user_id == user_id, RefreshSession.revoked_at.is_(None)
        )
    ):
        session.revoked_at = datetime.now(UTC)
