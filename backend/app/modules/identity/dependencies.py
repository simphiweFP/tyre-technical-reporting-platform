from collections.abc import Callable
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.database import get_db
from backend.app.core.security import decode_token
from backend.app.modules.identity.domain import Role
from backend.app.modules.identity.infrastructure import User

bearer = HTTPBearer(auto_error=False)


def current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if get_settings().auth_enabled:
        from backend.app.modules.identity.company_auth import company_user

        return company_user(request, db)
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise ValueError
        user = db.get(User, UUID(payload["sub"]))
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid access token") from exc
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User is inactive")
    return user


def require_roles(*roles: Role) -> Callable:
    def role_check(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permission")
        return user

    return role_check
