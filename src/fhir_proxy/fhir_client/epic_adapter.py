from typing import Any
from fhir_proxy.fhir_client.generic_adapter import GenericFhirAdapter


class EpicFhirAdapter(GenericFhirAdapter):
    CATEGORY_MAP = {
        "PT_Note": "clinical-note",
        "operative_note": "clinical-note",
        "case_management": "clinical-note",
        "nursing_page": "clinical-note",
        "imaging": "imaging",
        "pathology": "pathology",
    }

    async def search(self, resource_type: str, patient_id: str, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
        params = dict(params) if params else {}
        if resource_type == "DocumentReference" and "category" in params:
            internal_cat = params["category"]
            epic_cat = self.CATEGORY_MAP.get(internal_cat, internal_cat)
            params["category"] = epic_cat
        return await super().search(resource_type, patient_id, params)
