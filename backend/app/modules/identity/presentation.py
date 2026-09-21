from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.modules.identity.application import AuthenticationService
from backend.app.modules.identity.dependencies import current_user, require_roles
from backend.app.modules.identity.domain import Role
from backend.app.modules.identity.infrastructure import User
from backend.app.modules.identity.schemas import LoginRequest, LogoutRequest, RefreshRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user, access_token, refresh_token = AuthenticationService(db).login(request.email, request.password)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token, user=user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(request: RefreshRequest, db: Session = Depends(get_db)):
    user, access_token, refresh_token = AuthenticationService(db).refresh(request.refresh_token)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token, user=user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: LogoutRequest, db: Session = Depends(get_db)):
    AuthenticationService(db).logout(request.refresh_token)


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(current_user)):
    return user


@router.get("/admin-check", response_model=UserResponse)
def admin_check(user: User = Depends(require_roles(Role.ADMINISTRATOR))):
    return user
