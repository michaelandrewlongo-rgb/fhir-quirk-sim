import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from epic_sim.app import create_app
from epic_sim.fixtures import load_default_client


@pytest.fixture
def app():
    return create_app(fhir_client=load_default_client())


@pytest_asyncio.fixture
async def http_client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
