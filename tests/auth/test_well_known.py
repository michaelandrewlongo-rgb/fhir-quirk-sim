"""Verify `.well-known/smart-configuration` reflects quirk flags."""
import pytest
from httpx import ASGITransport, AsyncClient

from epic_sim.app import create_app
from epic_sim.config import SimulatorConfig


pytestmark = pytest.mark.asyncio


async def _get_config(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        resp = await c.get("/fhir/R4/.well-known/smart-configuration")
        return resp


async def test_omits_all_three_endpoints_by_default():
    app = create_app(
        config=SimulatorConfig(
            omit_introspection_endpoint=True,
            omit_revocation_endpoint=True,
            omit_registration_endpoint=True,
        )
    )
    resp = await _get_config(app)
    assert resp.status_code == 200
    body = resp.json()
    assert "introspection_endpoint" not in body
    assert "revocation_endpoint" not in body
    assert "registration_endpoint" not in body
    assert body["authorization_endpoint"].endswith("/fhir/R4/oauth2/authorize")
    assert body["token_endpoint"].endswith("/fhir/R4/oauth2/token")
    assert body["jwks_uri"].endswith("/fhir/R4/oauth2/jwks")


async def test_permissive_config_includes_all_endpoints():
    app = create_app(
        config=SimulatorConfig(
            omit_introspection_endpoint=False,
            omit_revocation_endpoint=False,
            omit_registration_endpoint=False,
        )
    )
    resp = await _get_config(app)
    body = resp.json()
    assert body["introspection_endpoint"].endswith("/introspect")
    assert body["revocation_endpoint"].endswith("/revoke")
    assert body["registration_endpoint"].endswith("/register")


async def test_jwks_endpoint_returns_public_key():
    app = create_app(config=SimulatorConfig())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        resp = await c.get("/fhir/R4/oauth2/jwks")
    body = resp.json()
    assert "keys" in body
    assert len(body["keys"]) == 1
    jwk = body["keys"][0]
    assert jwk["kty"] == "RSA"
    assert "n" in jwk and "e" in jwk
    assert "d" not in jwk  # private component must not leak
