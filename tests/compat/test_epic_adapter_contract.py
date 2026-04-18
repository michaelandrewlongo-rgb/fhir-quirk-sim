from unittest.mock import AsyncMock

import pytest

from fhir_proxy.fhir_client.epic_adapter import EpicFhirAdapter
from fhir_proxy.fhir_client.generic_adapter import GenericFhirAdapter


class TestEpicAdapterContract:
    async def test_maps_internal_note_category_to_epic_clinical_note(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        captured: dict = {}

        async def fake_search(self, resource_type, patient_id, params=None):
            captured["resource_type"] = resource_type
            captured["patient_id"] = patient_id
            captured["params"] = params
            return []

        monkeypatch.setattr(GenericFhirAdapter, "search", fake_search)

        adapter = EpicFhirAdapter(base_url="https://fhir.epic.example.com/api/FHIR/R4")
        adapter.client = AsyncMock()

        await adapter.search(
            resource_type="DocumentReference",
            patient_id="epic-patient-001",
            params={"category": "PT_Note"},
        )

        assert captured["resource_type"] == "DocumentReference"
        assert captured["patient_id"] == "epic-patient-001"
        assert captured["params"]["category"] == "clinical-note"

    async def test_preserves_observation_code_filters(self, monkeypatch: pytest.MonkeyPatch):
        captured: dict = {}

        async def fake_search(self, resource_type, patient_id, params=None):
            captured["params"] = params
            return []

        monkeypatch.setattr(GenericFhirAdapter, "search", fake_search)

        adapter = EpicFhirAdapter(base_url="https://fhir.epic.example.com/api/FHIR/R4")
        adapter.client = AsyncMock()

        await adapter.search(
            resource_type="Observation",
            patient_id="epic-patient-001",
            params={"code": "718-7,2951-2"},
        )

        assert captured["params"]["code"] == "718-7,2951-2"

