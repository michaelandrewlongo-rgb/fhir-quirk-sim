"""Backend-services JWT client assertion flow."""
import pytest

from tests.auth.conftest import make_client_assertion


pytestmark = pytest.mark.asyncio


AUDIENCE = "http://testserver/fhir/R4/oauth2/token"


async def test_happy_path_client_credentials_with_jwt_assertion(
    http_client, client_id, client_rsa_key
):
    assertion = make_client_assertion(client_id, AUDIENCE, client_rsa_key)
    resp = await http_client.post(
        "/fhir/R4/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": assertion,
            "scope": "system/*.read",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["token_type"] == "Bearer"
    assert body["access_token"]
    assert body["scope"] == "system/*.read"
    assert body["expires_in"] > 0


async def test_rejects_client_secret_when_jwt_required(http_client):
    resp = await http_client.post(
        "/fhir/R4/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": "anyone",
            "client_secret": "oops",
        },
    )
    assert resp.status_code == 401
    assert resp.json()["error"] == "invalid_client"


async def test_rejects_oversized_jti(http_client, client_id, client_rsa_key):
    long_jti = "x" * 152
    assertion = make_client_assertion(client_id, AUDIENCE, client_rsa_key, jti=long_jti)
    resp = await http_client.post(
        "/fhir/R4/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": assertion,
        },
    )
    assert resp.status_code == 401
    assert "jti" in resp.json()["error_description"]


async def test_rejects_exp_too_far_in_future(http_client, client_id, client_rsa_key):
    # Strict config allows 5 minutes; send 10 minutes out.
    assertion = make_client_assertion(
        client_id, AUDIENCE, client_rsa_key, exp_seconds_from_now=600
    )
    resp = await http_client.post(
        "/fhir/R4/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": assertion,
        },
    )
    assert resp.status_code == 401
    assert "exp" in resp.json()["error_description"]


async def test_rejects_jti_replay(http_client, client_id, client_rsa_key):
    assertion = make_client_assertion(
        client_id, AUDIENCE, client_rsa_key, jti="replay-jti-42"
    )
    first = await http_client.post(
        "/fhir/R4/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": assertion,
        },
    )
    assert first.status_code == 200

    # Replay the same assertion.
    second = await http_client.post(
        "/fhir/R4/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": assertion,
        },
    )
    assert second.status_code == 401
    assert "replay" in second.json()["error_description"]


async def test_rejects_unknown_client(http_client, client_rsa_key):
    assertion = make_client_assertion("unknown-client", AUDIENCE, client_rsa_key)
    resp = await http_client.post(
        "/fhir/R4/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": assertion,
        },
    )
    assert resp.status_code == 401
    assert "no registered key" in resp.json()["error_description"]


async def test_rejects_iss_sub_mismatch(http_client, client_id, client_rsa_key):
    assertion = make_client_assertion(
        client_id, AUDIENCE, client_rsa_key, override_sub="someone-else"
    )
    resp = await http_client.post(
        "/fhir/R4/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": assertion,
        },
    )
    assert resp.status_code == 401
    assert "iss must equal sub" in resp.json()["error_description"]


async def test_aud_allowlist_rejects_wrong_audience(
    http_client, client_id, client_rsa_key, app
):
    app.state.config.jwt_aud_allowlist = ["https://somewhere-else/token"]
    assertion = make_client_assertion(client_id, AUDIENCE, client_rsa_key)
    resp = await http_client.post(
        "/fhir/R4/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": assertion,
        },
    )
    assert resp.status_code == 401
    assert "aud" in resp.json()["error_description"]
