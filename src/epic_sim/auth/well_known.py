"""
SMART configuration endpoint.

Served at `/fhir/R4/.well-known/smart-configuration`. Respects the omit_* flags
on SimulatorConfig so tests can exercise clients that assume certain endpoints
exist when they actually do not (Q5 from docs/EPIC_QUIRKS.md).
"""
import json

from fastapi import APIRouter, Request
from fastapi.responses import Response

from epic_sim.config import SimulatorConfig


router = APIRouter()


def build_smart_configuration(base_url: str, config: SimulatorConfig) -> dict:
    doc = {
        "issuer": base_url,
        "jwks_uri": f"{base_url}/oauth2/jwks",
        "authorization_endpoint": f"{base_url}/oauth2/authorize",
        "token_endpoint": f"{base_url}/oauth2/token",
        "token_endpoint_auth_methods_supported": [
            "private_key_jwt",
            "client_secret_basic",
            "client_secret_post",
        ],
        "grant_types_supported": ["authorization_code", "client_credentials"],
        "scopes_supported": [
            "openid",
            "profile",
            "fhirUser",
            "launch",
            "launch/patient",
            "offline_access",
            "online_access",
            "patient/*.read",
            "user/*.read",
            "system/*.read",
        ],
        "response_types_supported": ["code"],
        "code_challenge_methods_supported": ["S256"],
        "capabilities": [
            "launch-ehr",
            "launch-standalone",
            "client-public",
            "client-confidential-symmetric",
            "client-confidential-asymmetric",
            "sso-openid-connect",
            "context-ehr-patient",
            "context-standalone-patient",
            "permission-offline",
            "permission-patient",
            "permission-user",
        ],
    }
    if not config.omit_introspection_endpoint:
        doc["introspection_endpoint"] = f"{base_url}/oauth2/introspect"
    if not config.omit_revocation_endpoint:
        doc["revocation_endpoint"] = f"{base_url}/oauth2/revoke"
    if not config.omit_registration_endpoint:
        doc["registration_endpoint"] = f"{base_url}/oauth2/register"
    return doc


@router.get("/.well-known/smart-configuration")
async def smart_configuration(request: Request) -> Response:
    config: SimulatorConfig = request.app.state.config
    base = str(request.base_url).rstrip("/") + "/fhir/R4"
    doc = build_smart_configuration(base, config)
    return Response(
        content=json.dumps(doc),
        media_type="application/json",
    )
