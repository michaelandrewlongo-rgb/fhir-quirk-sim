"""Auth-test fixtures. Each test gets a fresh app, fresh keys, and a fresh client."""
import time

import pytest
import pytest_asyncio
from authlib.jose import JsonWebKey, jwt
from httpx import ASGITransport, AsyncClient

from epic_sim.app import create_app
from epic_sim.config import SimulatorConfig


@pytest.fixture
def strict_config() -> SimulatorConfig:
    return SimulatorConfig(
        auth_required=True,
        backend_services_jwt_required=True,
        online_access_returns_offline=True,
        jwt_jti_max_length=151,
        jwt_exp_max_minutes=5,
        jwt_jti_replay_check=True,
        omit_introspection_endpoint=True,
        omit_revocation_endpoint=True,
        omit_registration_endpoint=True,
    )


@pytest.fixture
def client_rsa_key():
    return JsonWebKey.generate_key("RSA", 2048, is_private=True)


@pytest.fixture
def client_id() -> str:
    return "test-backend-client"


@pytest.fixture
def app(strict_config, client_id, client_rsa_key):
    a = create_app(config=strict_config)
    # Pre-register the test client's public JWK so the sim can verify assertions.
    public_jwk = client_rsa_key.as_dict(is_private=False)
    a.state.sim_keys.register_client_key(client_id, public_jwk)
    return a


@pytest_asyncio.fixture
async def http_client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


def make_client_assertion(
    client_id: str,
    audience: str,
    private_key,
    *,
    jti: str = "assertion-jti-1",
    exp_seconds_from_now: int = 120,
    override_iss: str | None = None,
    override_sub: str | None = None,
) -> str:
    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    payload = {
        "iss": override_iss if override_iss is not None else client_id,
        "sub": override_sub if override_sub is not None else client_id,
        "aud": audience,
        "jti": jti,
        "exp": now + exp_seconds_from_now,
        "iat": now,
    }
    token = jwt.encode(header, payload, private_key)
    return token.decode("ascii") if isinstance(token, bytes) else token
