"""Bearer-token dependency for FHIR routes. Gated by config.auth_required."""
from fastapi import Request

from epic_sim.auth.store import AccessTokenRecord, AccessTokenStore
from epic_sim.config import SimulatorConfig
from epic_sim.errors import FhirHTTPError


async def require_bearer(request: Request) -> AccessTokenRecord | None:
    config: SimulatorConfig = request.app.state.config
    if not config.auth_required:
        return None
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise FhirHTTPError(401, "login", "Missing bearer token")
    token = auth_header.split(" ", 1)[1].strip()
    store: AccessTokenStore = request.app.state.access_token_store
    record = store.get(token)
    if record is None:
        raise FhirHTTPError(401, "login", "Invalid or expired token")
    request.state.auth = record
    return record
