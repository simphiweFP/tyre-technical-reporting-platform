from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

import jwt
from pwdlib import PasswordHash

from backend.app.core.config import get_settings

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, password_digest: str) -> bool:
    return password_hash.verify(password, password_digest)


def create_token(
    subject: str, token_type: str, expires_delta: timedelta
) -> tuple[str, str, datetime]:
    settings = get_settings()
    expires_at = datetime.now(UTC) + expires_delta
    token_id = str(uuid4())
    payload = {"sub": subject, "type": token_type, "jti": token_id, "exp": expires_at}
    encoded = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return encoded, token_id, expires_at


def decode_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def token_digest(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()
