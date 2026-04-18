"""SMART EHR / standalone launch: authorize -> token -> bearer-gated FHIR call."""
import pytest
from httpx import ASGITransport, AsyncClient
from urllib.parse import parse_qs, urlparse

from epic_sim.app import create_app
from epic_sim.config import SimulatorConfig


pytestmark = pytest.mark.asyncio


@pytest.fixture
def auth_app():
    cfg = SimulatorConfig(auth_required=True, online_access_returns_offline=True)
    return create_app(config=cfg)


@pytest.fixture
async def auth_http(auth_app):
    transport = ASGITransport(app=auth_app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver", follow_redirects=False
    ) as c:
        yield c


async def test_authorize_redirects_with_code(auth_http):
    resp = await auth_http.get(
        "/fhir/R4/oauth2/authorize",
        params={
            "client_id": "demo-client",
            "redirect_uri": "http://app.example/cb",
            "response_type": "code",
            "scope": "launch openid online_access patient/*.read",
            "state": "xyz123",
            "launch_patient": "epic-patient-001",
            "launch_fhir_user": "Practitioner/prac-001",
        },
    )
    assert resp.status_code == 302
    target = urlparse(resp.headers["location"])
    qs = parse_qs(target.query)
    assert qs["code"]
    assert qs["state"] == ["xyz123"]


async def test_full_authorize_to_token_to_fhir_call(auth_http):
    # Step 1: authorize.
    resp = await auth_http.get(
        "/fhir/R4/oauth2/authorize",
        params={
            "client_id": "demo-client",
            "redirect_uri": "http://app.example/cb",
            "response_type": "code",
            "scope": "launch openid online_access patient/*.read",
            "state": "abc",
            "launch_patient": "epic-patient-001",
        },
    )
    code = parse_qs(urlparse(resp.headers["location"]).query)["code"][0]

    # Step 2: exchange code for access token.
    token_resp = await auth_http.post(
        "/fhir/R4/oauth2/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "http://app.example/cb",
            "client_id": "demo-client",
        },
    )
    assert token_resp.status_code == 200, token_resp.text
    body = token_resp.json()
    assert body["token_type"] == "Bearer"
    access_token = body["access_token"]
    assert body["patient"] == "epic-patient-001"
    # online_access must have been swapped to offline_access (Q3).
    assert "offline_access" in body["scope"]
    assert "online_access" not in body["scope"]

    # Step 3: use bearer on a FHIR call.
    fhir_resp = await auth_http.get(
        "/fhir/R4/Observation",
        params={"patient": "epic-patient-001"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert fhir_resp.status_code == 200
    bundle = fhir_resp.json()
    assert bundle["resourceType"] == "Bundle"


async def test_fhir_call_without_bearer_rejected(auth_http):
    resp = await auth_http.get(
        "/fhir/R4/Observation", params={"patient": "epic-patient-001"}
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["resourceType"] == "OperationOutcome"
    assert body["issue"][0]["code"] == "login"


async def test_bad_bearer_rejected(auth_http):
    resp = await auth_http.get(
        "/fhir/R4/Observation",
        params={"patient": "epic-patient-001"},
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert resp.status_code == 401


async def test_code_single_use(auth_http):
    resp = await auth_http.get(
        "/fhir/R4/oauth2/authorize",
        params={
            "client_id": "demo-client",
            "redirect_uri": "http://app.example/cb",
            "response_type": "code",
        },
    )
    code = parse_qs(urlparse(resp.headers["location"]).query)["code"][0]
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": "http://app.example/cb",
        "client_id": "demo-client",
    }
    first = await auth_http.post("/fhir/R4/oauth2/token", data=data)
    assert first.status_code == 200
    second = await auth_http.post("/fhir/R4/oauth2/token", data=data)
    assert second.status_code == 400
    assert second.json()["error"] == "invalid_grant"


async def test_auth_optional_when_config_disables(monkeypatch):
    # auth_required=False: Phase 1 behavior preserved, no bearer needed.
    app = create_app(config=SimulatorConfig(auth_required=False))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        resp = await c.get(
            "/fhir/R4/Observation", params={"patient": "epic-patient-001"}
        )
    assert resp.status_code == 200
