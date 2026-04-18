"""
In-memory stores for auth codes, access tokens, and seen JWT jti values.

These are dev-simulator primitives. No persistence: everything resets on app
restart. All stores enforce TTL-based expiry.
"""
from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass, field

from epic_sim.auth.context import LaunchContext


@dataclass
class AuthCodeRecord:
    client_id: str
    redirect_uri: str
    scope: str
    launch_context: LaunchContext
    expires_at: float
    code_challenge: str | None = None
    code_challenge_method: str | None = None


@dataclass
class AccessTokenRecord:
    client_id: str
    scope: str
    launch_context: LaunchContext
    expires_at: float


class AuthCodeStore:
    def __init__(self, ttl_seconds: int = 60) -> None:
        self.ttl = ttl_seconds
        self._records: dict[str, AuthCodeRecord] = {}

    def issue(
        self,
        client_id: str,
        redirect_uri: str,
        scope: str,
        launch_context: LaunchContext,
        code_challenge: str | None = None,
        code_challenge_method: str | None = None,
    ) -> str:
        code = secrets.token_urlsafe(32)
        self._records[code] = AuthCodeRecord(
            client_id=client_id,
            redirect_uri=redirect_uri,
            scope=scope,
            launch_context=launch_context,
            expires_at=time.time() + self.ttl,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
        )
        return code

    def consume(self, code: str) -> AuthCodeRecord | None:
        """Auth codes are single-use. Returns None if missing/expired/already-consumed."""
        record = self._records.pop(code, None)
        if record is None:
            return None
        if time.time() > record.expires_at:
            return None
        return record


class AccessTokenStore:
    def __init__(self, ttl_seconds: int = 3600) -> None:
        self.ttl = ttl_seconds
        self._records: dict[str, AccessTokenRecord] = {}

    def issue(
        self,
        client_id: str,
        scope: str,
        launch_context: LaunchContext,
        ttl_seconds: int | None = None,
    ) -> tuple[str, AccessTokenRecord]:
        token = secrets.token_urlsafe(32)
        ttl = ttl_seconds if ttl_seconds is not None else self.ttl
        record = AccessTokenRecord(
            client_id=client_id,
            scope=scope,
            launch_context=launch_context,
            expires_at=time.time() + ttl,
        )
        self._records[token] = record
        return token, record

    def get(self, token: str) -> AccessTokenRecord | None:
        record = self._records.get(token)
        if record is None:
            return None
        if time.time() > record.expires_at:
            self._records.pop(token, None)
            return None
        return record


@dataclass
class JtiStore:
    """Tracks used JWT jti values to enforce replay protection within their exp window."""
    _seen: dict[str, float] = field(default_factory=dict)

    def check_and_record(self, jti: str, exp: float) -> bool:
        """Return False if jti already seen (and still within its exp). Otherwise record and return True."""
        now = time.time()
        # Lazy GC of expired entries.
        stale = [k for k, v in self._seen.items() if v < now]
        for k in stale:
            self._seen.pop(k, None)
        if jti in self._seen:
            return False
        self._seen[jti] = exp
        return True
