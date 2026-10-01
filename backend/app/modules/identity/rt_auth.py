import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode

import httpx
import jwt
from jwt import PyJWK

from backend.app.core.config import Settings


class RTAuthError(RuntimeError):
    pass


class RTAuthClient:
    _jwks: dict[str, dict] = {}
    _jwks_expires_at = 0.0

    def __init__(self, settings: Settings):
        self.settings = settings

    @staticmethod
    def pkce_verifier() -> str:
        return secrets.token_urlsafe(64)

    @staticmethod
    def pkce_challenge(verifier: str) -> str:
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    def authorize_url(self, state: str, verifier: str) -> str:
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self.settings.auth_client_id,
                "redirect_uri": self.settings.auth_redirect_uri,
                "state": state,
                "code_challenge": self.pkce_challenge(verifier),
                "code_challenge_method": "S256",
            }
        )
        return f"{self.settings.auth_issuer_url.rstrip('/')}/authorize?{query}"

    def exchange_code(self, code: str, verifier: str) -> dict:
        response = self._client().post(
            f"{self.settings.auth_issuer_url.rstrip('/')}/token",
            auth=(self.settings.auth_client_id, self.settings.auth_client_secret),
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.settings.auth_redirect_uri,
                "code_verifier": verifier,
            },
        )
        if response.status_code >= 400:
            raise RTAuthError("RT-Auth rejected the authorization code exchange")
        payload = response.json()
        if not payload.get("id_token") or not payload.get("refresh_token"):
            raise RTAuthError("RT-Auth token response is incomplete")
        return payload

    def validate_id_token(self, token: str) -> dict:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise RTAuthError("RT-Auth returned an invalid id_token") from exc

        if header.get("alg") != "RS256":
            raise RTAuthError("RT-Auth id_token must use RS256")
        kid = str(header.get("kid") or "")
        if not kid:
            raise RTAuthError("RT-Auth id_token is missing kid")

        key_data = self._key_for(kid)
        try:
            claims = jwt.decode(
                token,
                PyJWK.from_dict(key_data).key,
                algorithms=["RS256"],
                audience=self.settings.auth_client_id,
                issuer=self.settings.auth_issuer_url,
                leeway=10,
            )
        except jwt.PyJWTError as exc:
            raise RTAuthError("RT-Auth id_token validation failed") from exc

        if claims.get("typ") != "id_token":
            raise RTAuthError("RT-Auth token has an invalid type")
        if not claims.get("sub") or not claims.get("email"):
            raise RTAuthError("RT-Auth id_token is missing identity claims")
        return claims

    def revoke(self, refresh_token: str) -> None:
        response = self._client().post(
            f"{self.settings.auth_issuer_url.rstrip('/')}/revoke",
            auth=(self.settings.auth_client_id, self.settings.auth_client_secret),
            data={"refresh_token": refresh_token},
        )
        if response.status_code >= 400:
            raise RTAuthError("RT-Auth refresh token revocation failed")

    def _key_for(self, kid: str) -> dict:
        now = time.time()
        if now >= self._jwks_expires_at:
            self._refresh_jwks()
        key = self._jwks.get(kid)
        if key is None:
            self._refresh_jwks()
            key = self._jwks.get(kid)
        if key is None:
            raise RTAuthError("RT-Auth signing key was not found")
        return key

    def _refresh_jwks(self) -> None:
        response = self._client().get(
            f"{self.settings.auth_issuer_url.rstrip('/')}/.well-known/jwks.json"
        )
        if response.status_code >= 400:
            raise RTAuthError("Could not load RT-Auth signing keys")
        keys = response.json().get("keys") or []
        self.__class__._jwks = {
            str(key.get("kid")): key for key in keys if key.get("kid")
        }
        self.__class__._jwks_expires_at = time.time() + 3600

    def _client(self) -> httpx.Client:
        verify: bool | str = self.settings.auth_root_ca_path or True
        return httpx.Client(verify=verify, timeout=20.0)
