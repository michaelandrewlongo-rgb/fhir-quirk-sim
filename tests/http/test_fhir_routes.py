"""HTTP-level tests for the Phase 1 FastAPI surface."""
import pytest

from httpx import AsyncClient, ASGITransport

from epic_sim.app import create_app
from epic_sim.fixtures import FixtureFhirClient, load_default_client, load_epic_fixture


pytestmark = pytest.mark.asyncio


class TestCapabilityStatement:
    async def test_metadata_returns_capability_statement(self, http_client: AsyncClient):
        resp = await http_client.get("/fhir/R4/metadata")
        assert resp.status_code == 200
        body = resp.json()
        assert body["resourceType"] == "CapabilityStatement"
        assert body["fhirVersion"] == "4.0.1"
        assert resp.headers["content-type"].startswith("application/fhir+json")


class TestSearch:
    async def test_observation_search_returns_epic_shaped_bundle(self, http_client: AsyncClient):
        resp = await http_client.get(
            "/fhir/R4/Observation", params={"patient": "epic-patient-001"}
        )
        assert resp.status_code == 200
        bundle = resp.json()
        assert bundle["resourceType"] == "Bundle"
        assert bundle["type"] == "searchset"
        assert bundle["total"] >= 1
        assert any(link["relation"] == "self" for link in bundle["link"])
        entry_full_urls = [entry["fullUrl"] for entry in bundle["entry"]]
        assert all(url.endswith(f"/fhir/R4/Observation/{entry['resource']['id']}")
                   for url, entry in zip(entry_full_urls, bundle["entry"]))

    async def test_search_requires_patient_param(self, http_client: AsyncClient):
        resp = await http_client.get("/fhir/R4/Observation")
        assert resp.status_code == 400
        body = resp.json()
        assert body["resourceType"] == "OperationOutcome"
        assert body["issue"][0]["code"] == "required"

    async def test_observation_code_filter_narrows_results(self, http_client: AsyncClient):
        resp = await http_client.get(
            "/fhir/R4/Observation",
            params={"patient": "epic-patient-001", "code": "718-7"},
        )
        assert resp.status_code == 200
        bundle = resp.json()
        assert bundle["total"] == 1
        assert bundle["entry"][0]["resource"]["id"] == "epic-obs-hgb-001"

    async def test_unsupported_search_param_returns_operation_outcome(self):
        client = FixtureFhirClient(
            search_bundles={
                "Observation": load_epic_fixture("observations_labs_bundle.json"),
            },
            binary_resources={},
            unsupported_searches={("Observation", "category")},
        )
        app = create_app(fhir_client=client)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as http:
            resp = await http.get(
                "/fhir/R4/Observation",
                params={"patient": "epic-patient-001", "category": "laboratory"},
            )
        assert resp.status_code == 400
        body = resp.json()
        assert body["resourceType"] == "OperationOutcome"
        assert body["issue"][0]["code"] == "not-supported"


class TestRead:
    async def test_read_observation_by_id(self, http_client: AsyncClient):
        resp = await http_client.get("/fhir/R4/Observation/epic-obs-hgb-001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["resourceType"] == "Observation"
        assert body["id"] == "epic-obs-hgb-001"

    async def test_read_unknown_id_returns_operation_outcome_404(self, http_client: AsyncClient):
        resp = await http_client.get("/fhir/R4/Observation/does-not-exist")
        assert resp.status_code == 404
        body = resp.json()
        assert body["resourceType"] == "OperationOutcome"
        assert body["issue"][0]["code"] == "not-found"


class TestBinary:
    async def test_read_binary_returns_base64_resource(self, http_client: AsyncClient):
        resp = await http_client.get("/fhir/R4/Binary/epic-note-001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["resourceType"] == "Binary"
        assert body["id"] == "epic-note-001"
        assert "data" in body and body["data"]

    async def test_forbidden_binary_returns_403_operation_outcome(self):
        client = FixtureFhirClient(
            search_bundles={},
            binary_resources={"epic-note-001": load_epic_fixture("binary_note_success.json")},
            forbidden_binaries={"epic-note-001"},
        )
        app = create_app(fhir_client=client)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as http:
            resp = await http.get("/fhir/R4/Binary/epic-note-001")
        assert resp.status_code == 403
        body = resp.json()
        assert body["resourceType"] == "OperationOutcome"
        assert body["issue"][0]["code"] == "forbidden"

    async def test_unknown_binary_returns_404(self, http_client: AsyncClient):
        resp = await http_client.get("/fhir/R4/Binary/nope")
        assert resp.status_code == 404


class TestAdapterReachesHttpSurface:
    """Prove GenericFhirAdapter can drive the simulator with just a base-URL swap."""

    async def test_generic_adapter_searches_sim(self, app):
        from fhir_proxy.fhir_client.generic_adapter import GenericFhirAdapter

        adapter = GenericFhirAdapter(base_url="http://testserver/fhir/R4")
        # Replace its httpx client with one that routes into the ASGI app.
        transport = ASGITransport(app=app)
        adapter.client = AsyncClient(transport=transport, base_url="http://testserver/fhir/R4")

        resources = await adapter.search("Observation", patient_id="epic-patient-001")

        assert len(resources) >= 1
        assert any(r.get("id") == "epic-obs-hgb-001" for r in resources)
        await adapter.close()
