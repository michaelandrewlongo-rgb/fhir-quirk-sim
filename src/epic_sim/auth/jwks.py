"""
Signing keys for the simulator, plus a registry of client public keys used to
verify JWT client assertions in the backend-services flow.
"""
from __future__ import annotations

from typing import Any

from authlib.jose import JsonWebKey, jwt


class SimKeys:
    """The simulator's own RSA key pair + a registry of client public keys."""

    def __init__(self, kid: str = "epic-sim-key-1") -> None:
        self.private_key = JsonWebKey.generate_key("RSA", 2048, is_private=True)
        public_dict = self.private_key.as_dict(is_private=False)
        public_dict.setdefault("kid", kid)
        public_dict.setdefault("use", "sig")
        public_dict.setdefault("alg", "RS256")
        self._public_jwk = public_dict
        # Client public keys stored as JWK dicts. authlib's jwt.decode accepts dict keys.
        self._client_keys: dict[str, dict] = {}

    def public_jwks(self) -> dict:
        return {"keys": [self._public_jwk]}

    def sign_jwt(self, payload: dict, *, extra_header: dict | None = None) -> str:
        header = {"alg": "RS256", "typ": "JWT", "kid": self._public_jwk["kid"]}
        if extra_header:
            header.update(extra_header)
        token = jwt.encode(header, payload, self.private_key)
        return token.decode("ascii") if isinstance(token, bytes) else token

    def register_client_key(self, client_id: str, jwk: dict) -> None:
        """Register a client's public JWK. Used to verify their JWT client assertions."""
        if not isinstance(jwk, dict):
            jwk = jwk.as_dict(is_private=False)
        self._client_keys[client_id] = jwk

    def get_client_key(self, client_id: str) -> dict | None:
        return self._client_keys.get(client_id)
