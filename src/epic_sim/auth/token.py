"""
`/oauth2/token` — OAuth2 token endpoint supporting both
- `authorization_code` grant (SMART EHR / standalone launch)
- `client_credentials` grant with JWT client assertion (backend services)

Quirk flags driving behavior (see docs/EPIC_QUIRKS.md):
- backend_services_jwt_required — reject client_secret_basic for client_credentials
- auth_code_format — opaque vs jwt-shaped authorization codes
- online_access_returns_offline — swap online_access → offline_access in responses
- fhir_user_in_id_token — put fhirUser claim in id_token
- jwt_jti_max_length — reject assertions with oversized jti
- jwt_exp_max_minutes — reject assertions whose exp is too far in the future
- jwt_jti_replay_check — reject reused jti within its exp window
- jwt_aud_allowlist — if set, audience must match one of these values
"""
from __future__ import annotations

import json
import time

import base64

from authlib.jose import jwt
from authlib.jose.errors import JoseError
from fastapi import APIRouter, Form, Request
from fastapi.responses import Response

from epic_sim.auth.context import LaunchContext
from epic_sim.auth.jwks import SimKeys
from epic_sim.auth.store import AccessTokenStore, AuthCodeStore, JtiStore
from epic_sim.config import SimulatorConfig
from epic_sim.errors import FhirHTTPError


router = APIRouter()


def _oauth_error(status_code: int, error: str, description: str) -> Response:
    return Response(
        content=json.dumps({"error": error, "error_description": description}),
        status_code=status_code,
        media_type="application/json",
    )


def _swap_scopes(requested: str, online_to_offline: bool) -> str:
    if not online_to_offline:
        return requested
    parts = requested.split()
    swapped = ["offline_access" if p == "online_access" else p for p in parts]
    # de-dup while preserving order
    seen: set[str] = set()
    out = []
    for p in swapped:
        if p not in seen:
            out.append(p)
            seen.add(p)
    return " ".join(out)


def _token_response(
    access_token: str,
    scope: str,
    ttl_seconds: int,
    launch_context: LaunchContext,
    id_token: str | None = None,
) -> dict:
    body = {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": ttl_seconds,
        "scope": scope,
    }
    body.update(launch_context.to_token_extras())
    if id_token:
        body["id_token"] = id_token
    return body


def _validate_jwt_assertion(
    assertion: str,
    request: Request,
    config: SimulatorConfig,
) -> tuple[str, dict]:
    """
    Verify a client JWT assertion per Epic's quirks. Returns (client_id, claims).
    Raises FhirHTTPError on any validation failure.
    """
    sim_keys: SimKeys = request.app.state.sim_keys
    jti_store: JtiStore = request.app.state.jti_store

    # Peek at claims (no signature verification) to find the issuer → client_id.
    parts = assertion.split(".")
    if len(parts) != 3:
        raise FhirHTTPError(401, "invalid", "malformed JWT assertion")
    try:
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        peeked = json.loads(base64.urlsafe_b64decode(padded))
    except Exception:
        raise FhirHTTPError(401, "invalid", "unparseable JWT payload")
    client_id = peeked.get("iss")
    if not client_id:
        raise FhirHTTPError(401, "invalid", "assertion missing iss")

    client_key = sim_keys.get_client_key(client_id)
    if client_key is None:
        raise FhirHTTPError(401, "unknown", f"no registered key for client {client_id}")

    try:
        claims = jwt.decode(assertion, key=client_key)
    except JoseError:
        raise FhirHTTPError(401, "invalid", "signature verification failed")

    now = time.time()
    exp = claims.get("exp")
    if exp is None or exp < now:
        raise FhirHTTPError(401, "invalid", "assertion expired or missing exp")
    if exp > now + config.jwt_exp_max_minutes * 60:
        raise FhirHTTPError(
            401,
            "invalid",
            f"exp is more than {config.jwt_exp_max_minutes} minutes in the future",
        )
    sub = claims.get("sub")
    if sub != client_id:
        raise FhirHTTPError(401, "invalid", "iss must equal sub")
    jti = claims.get("jti")
    if not jti:
        raise FhirHTTPError(401, "invalid", "jti required")
    if len(jti) > config.jwt_jti_max_length:
        raise FhirHTTPError(
            401, "invalid", f"jti exceeds max length {config.jwt_jti_max_length}"
        )
    aud = claims.get("aud")
    if config.jwt_aud_allowlist and aud not in config.jwt_aud_allowlist:
        raise FhirHTTPError(401, "invalid", "aud not in allowlist")
    if config.jwt_jti_replay_check:
        if not jti_store.check_and_record(jti, float(exp)):
            raise FhirHTTPError(401, "invalid", "jti replay detected")

    return client_id, dict(claims)


@router.post("/token")
async def token_endpoint(
    request: Request,
    grant_type: str = Form(...),
    code: str | None = Form(None),
    redirect_uri: str | None = Form(None),
    client_id: str | None = Form(None),
    client_secret: str | None = Form(None),
    scope: str | None = Form(None),
    client_assertion: str | None = Form(None),
    client_assertion_type: str | None = Form(None),
    code_verifier: str | None = Form(None),
) -> Response:
    config: SimulatorConfig = request.app.state.config
    access_token_store: AccessTokenStore = request.app.state.access_token_store

    if grant_type == "authorization_code":
        if not code or not redirect_uri or not client_id:
            return _oauth_error(400, "invalid_request", "code, redirect_uri, client_id required")
        auth_code_store: AuthCodeStore = request.app.state.auth_code_store
        record = auth_code_store.consume(code)
        if record is None:
            return _oauth_error(400, "invalid_grant", "unknown, consumed, or expired code")
        if record.client_id != client_id:
            return _oauth_error(400, "invalid_grant", "code does not match client_id")
        if record.redirect_uri != redirect_uri:
            return _oauth_error(400, "invalid_grant", "redirect_uri mismatch")
        granted_scope = _swap_scopes(record.scope, config.online_access_returns_offline)
        token, _ = access_token_store.issue(
            client_id=record.client_id,
            scope=granted_scope,
            launch_context=record.launch_context,
        )
        body = _token_response(
            access_token=token,
            scope=granted_scope,
            ttl_seconds=access_token_store.ttl,
            launch_context=record.launch_context,
            id_token=_maybe_mint_id_token(request, record.client_id, record.launch_context, config),
        )
        return Response(
            content=json.dumps(body),
            media_type="application/json",
        )

    if grant_type == "client_credentials":
        # Reject client_secret path when backend_services_jwt_required is on.
        if config.backend_services_jwt_required:
            if client_secret or not client_assertion or not client_assertion_type:
                return _oauth_error(
                    401,
                    "invalid_client",
                    "backend services requires JWT assertion (client_assertion)",
                )
            if (
                client_assertion_type
                != "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
            ):
                return _oauth_error(
                    401, "invalid_client", "unsupported client_assertion_type"
                )
        if client_assertion:
            try:
                verified_client_id, _claims = _validate_jwt_assertion(
                    client_assertion, request, config
                )
            except FhirHTTPError as exc:
                detail = (
                    exc.detail["issue"][0]["diagnostics"]
                    if isinstance(exc.detail, dict)
                    else str(exc.detail)
                )
                return _oauth_error(exc.status_code, "invalid_client", detail)
            effective_client_id = verified_client_id
        else:
            if not client_id:
                return _oauth_error(400, "invalid_request", "client_id required")
            effective_client_id = client_id

        granted_scope = scope or "system/*.read"
        token, _ = access_token_store.issue(
            client_id=effective_client_id,
            scope=granted_scope,
            launch_context=LaunchContext(),
        )
        body = _token_response(
            access_token=token,
            scope=granted_scope,
            ttl_seconds=access_token_store.ttl,
            launch_context=LaunchContext(),
        )
        return Response(content=json.dumps(body), media_type="application/json")

    return _oauth_error(400, "unsupported_grant_type", f"grant_type={grant_type}")


def _maybe_mint_id_token(
    request: Request,
    client_id: str,
    launch_context: LaunchContext,
    config: SimulatorConfig,
) -> str | None:
    if not launch_context.fhir_user and not config.fhir_user_in_id_token:
        return None
    sim_keys: SimKeys = request.app.state.sim_keys
    now = int(time.time())
    payload: dict = {
        "iss": str(request.base_url).rstrip("/") + "/fhir/R4",
        "aud": client_id,
        "sub": launch_context.fhir_user or "unknown",
        "iat": now,
        "exp": now + 3600,
    }
    if config.fhir_user_in_id_token and launch_context.fhir_user:
        payload["fhirUser"] = launch_context.fhir_user
    return sim_keys.sign_jwt(payload)


@router.get("/jwks")
async def jwks(request: Request) -> Response:
    sim_keys: SimKeys = request.app.state.sim_keys
    return Response(
        content=json.dumps(sim_keys.public_jwks()),
        media_type="application/json",
    )
