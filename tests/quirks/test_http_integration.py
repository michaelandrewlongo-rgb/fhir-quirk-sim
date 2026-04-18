"""End-to-end: quirk flags visibly change HTTP responses."""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from epic_sim.app import create_app
from epic_sim.config import SimulatorConfig
from epic_sim.fixtures import load_default_client


pytestmark = pytest.mark.asyncio


def _make_client(config: SimulatorConfig):
    app = create_app(fhir_client=load_default_client(), config=config)
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


async def test_since_rejected_by_default():
    async with _make_client(SimulatorConfig()) as c:
        resp = await c.get(
            "/fhir/R4/Observation",
            params={"patient": "epic-patient-001", "_since": "2024-01-01"},
        )
    assert resp.status_code == 400
    assert resp.json()["resourceType"] == "OperationOutcome"


async def test_since_allowed_when_bulk_since_supported():
    cfg = SimulatorConfig(bulk_since_supported=True, post_filter_enabled=False)
    async with _make_client(cfg) as c:
        resp = await c.get(
            "/fhir/R4/Observation",
            params={"patient": "epic-patient-001", "_since": "2024-01-01"},
        )
    assert resp.status_code == 200


async def test_docref_data_stripped_by_default():
    async with _make_client(SimulatorConfig(post_filter_enabled=False)) as c:
        resp = await c.get(
            "/fhir/R4/DocumentReference", params={"patient": "epic-patient-001"}
        )
    bundle = resp.json()
    for entry in bundle["entry"]:
        for item in entry["resource"].get("content", []):
            assert "data" not in item.get("attachment", {})


async def test_docref_binary_url_preserved():
    # Stripping data must not also strip the Binary URL — clients need the URL
    # to dereference.
    async with _make_client(SimulatorConfig(post_filter_enabled=False)) as c:
        resp = await c.get(
            "/fhir/R4/DocumentReference", params={"patient": "epic-patient-001"}
        )
    bundle = resp.json()
    had_url = any(
        "url" in item.get("attachment", {})
        for entry in bundle["entry"]
        for item in entry["resource"].get("content", [])
    )
    assert had_url


async def test_vip_patient_blocks_request():
    cfg = SimulatorConfig(vip_patient_ids=["epic-patient-001"])
    async with _make_client(cfg) as c:
        resp = await c.get(
            "/fhir/R4/Observation", params={"patient": "epic-patient-001"}
        )
    assert resp.status_code == 403


async def test_permissive_preserves_vanilla_shape():
    cfg = SimulatorConfig(
        post_filter_enabled=False,
        observation_include_epic_local_code=False,
        observation_include_has_member=True,
        populate_meta_last_updated=True,
        unsupported_param_behavior="ignore",
    )
    async with _make_client(cfg) as c:
        resp = await c.get(
            "/fhir/R4/Observation", params={"patient": "epic-patient-001"}
        )
    bundle = resp.json()
    for entry in bundle["entry"]:
        codings = entry["resource"].get("code", {}).get("coding", [])
        assert all(c.get("system") != cfg.epic_local_code_system for c in codings)


async def test_max_page_size_caps_bundle():
    cfg = SimulatorConfig(max_page_size=1, post_filter_enabled=False)
    async with _make_client(cfg) as c:
        resp = await c.get(
            "/fhir/R4/Observation", params={"patient": "epic-patient-001"}
        )
    bundle = resp.json()
    assert len(bundle["entry"]) <= 1
