"""
`/oauth2/authorize` — SMART app launch code issuance.

For a dev simulator we skip the interactive picker and accept launch context
via query parameters (`launch_patient`, `launch_encounter`, `launch_fhir_user`).
The endpoint issues a single-use authorization code and redirects to the
client's redirect_uri with `code` and `state`.
"""
from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from epic_sim.auth.context import LaunchContext


router = APIRouter()


@router.get("/authorize")
async def authorize(request: Request) -> RedirectResponse:
    from epic_sim.errors import FhirHTTPError

    params = dict(request.query_params)
    client_id = params.get("client_id")
    redirect_uri = params.get("redirect_uri")
    scope = params.get("scope", "")
    state = params.get("state")
    response_type = params.get("response_type", "code")
    code_challenge = params.get("code_challenge")
    code_challenge_method = params.get("code_challenge_method")
    if not client_id or not redirect_uri:
        raise FhirHTTPError(400, "required", "client_id and redirect_uri required")
    if response_type != "code":
        raise FhirHTTPError(400, "not-supported", "only response_type=code is supported")

    launch_context = LaunchContext(
        patient=params.get("launch_patient"),
        encounter=params.get("launch_encounter"),
        fhir_user=params.get("launch_fhir_user"),
    )

    auth_code_store = request.app.state.auth_code_store
    code = auth_code_store.issue(
        client_id=client_id,
        redirect_uri=redirect_uri,
        scope=scope,
        launch_context=launch_context,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
    )
    query = {"code": code}
    if state:
        query["state"] = state
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(url=f"{redirect_uri}{sep}{urlencode(query)}", status_code=302)
