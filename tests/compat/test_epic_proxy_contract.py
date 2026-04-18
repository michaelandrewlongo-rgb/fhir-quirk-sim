import pytest

from fhir_proxy.deid.token_store import TokenStore
from fhir_proxy.executor import FetchPlanExecutor
from fhir_proxy.models.fetch_plan import FetchPlan, FetchPlanItem

from tests.compat.conftest import FixtureFhirClient, load_epic_fixture


class TestEpicProxyContract:
    async def test_fetches_epic_shaped_labs_and_deidentifies_display_names(
        self, epic_fixture_client
    ):
        store = TokenStore(session_id="epic-session-001")
        executor = FetchPlanExecutor(fhir_client=epic_fixture_client, token_store=store)
        plan = FetchPlan(
            session_id="epic-session-001",
            patient_id="epic-patient-001",
            items=[
                FetchPlanItem(
                    resource_type="Observation",
                    codes=["718-7", "2951-2"],
                )
            ],
        )

        bundle = await executor.execute(plan)

        assert bundle.errors == []
        assert {resource.source_ref for resource in bundle.resources} == {
            "Observation/epic-obs-hgb-001",
            "Observation/epic-obs-na-001",
        }
        assert "Jordan Example" not in str([resource.data for resource in bundle.resources])
        assert any("<<patient_name_" in str(resource.data) for resource in bundle.resources)

    async def test_fetches_epic_document_reference_binary_and_strips_html(
        self, epic_fixture_client
    ):
        store = TokenStore(session_id="epic-session-002")
        executor = FetchPlanExecutor(fhir_client=epic_fixture_client, token_store=store)
        plan = FetchPlan(
            session_id="epic-session-002",
            patient_id="epic-patient-001",
            items=[FetchPlanItem(resource_type="DocumentReference", category="clinical-note")],
        )

        bundle = await executor.execute(plan)

        assert bundle.errors == []
        assert len(bundle.resources) == 1
        note = bundle.resources[0].content_text
        assert note is not None
        assert "<p>" not in note
        assert "Assessment:" in note
        assert "Plan:" in note
        assert epic_fixture_client.binary_calls == ["Binary/epic-note-001"]

    async def test_binary_denial_keeps_document_reference_and_records_error(self):
        client = FixtureFhirClient(
            search_bundles={
                "DocumentReference": load_epic_fixture("document_reference_bundle.json"),
            },
            binary_resources={
                "epic-note-001": load_epic_fixture("binary_note_success.json"),
            },
            forbidden_binaries={"epic-note-001"},
        )
        store = TokenStore(session_id="epic-session-003")
        executor = FetchPlanExecutor(fhir_client=client, token_store=store)
        plan = FetchPlan(
            session_id="epic-session-003",
            patient_id="epic-patient-001",
            items=[FetchPlanItem(resource_type="DocumentReference", category="clinical-note")],
        )

        bundle = await executor.execute(plan)

        assert len(bundle.resources) == 1
        assert bundle.resources[0].content_text is None
        assert any("Access denied for Binary read" in error for error in bundle.errors)

    async def test_unsupported_epic_search_param_becomes_bundle_error(self):
        client = FixtureFhirClient(
            search_bundles={
                "Observation": load_epic_fixture("observations_labs_bundle.json"),
            },
            binary_resources={},
            unsupported_searches={("Observation", "category")},
        )
        store = TokenStore(session_id="epic-session-004")
        executor = FetchPlanExecutor(fhir_client=client, token_store=store)
        plan = FetchPlan(
            session_id="epic-session-004",
            patient_id="epic-patient-001",
            items=[
                FetchPlanItem(
                    resource_type="Observation",
                    category="laboratory",
                )
            ],
        )

        bundle = await executor.execute(plan)

        assert bundle.resources == []
        assert any("not supported" in error for error in bundle.errors)


@pytest.mark.asyncio
async def test_epic_vertical_slice_with_stubbed_synthesis(epic_fixture_client):
    store = TokenStore(session_id="epic-session-vertical")
    executor = FetchPlanExecutor(fhir_client=epic_fixture_client, token_store=store)
    plan = FetchPlan(
        session_id="epic-session-vertical",
        patient_id="epic-patient-001",
        items=[
            FetchPlanItem(resource_type="Observation", codes=["718-7"]),
            FetchPlanItem(resource_type="DocumentReference", category="clinical-note"),
        ],
    )

    bundle = await executor.execute(plan)
    source_refs = {resource.source_ref for resource in bundle.resources}

    assert bundle.errors == []
    assert "Observation/epic-obs-hgb-001" in source_refs
    assert "DocumentReference/epic-docref-001" in source_refs
    assert any(resource.content_text for resource in bundle.resources)
