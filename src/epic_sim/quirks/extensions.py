"""
Epic-specific extension / coding quirks.

- observation_include_epic_local_code → add Epic local-code Coding alongside LOINC
  in Observation.code.coding. Epic pins a local OID.
- patient_gender_identity_extension → add the Epic gender identity extension to
  Patient when present. We only inject a placeholder so client code learns to
  read the URL — real values should come from captured fixtures.
- medication_request_epic_category → add MedicationRequest.category coding.
"""
from __future__ import annotations

from typing import Any

from epic_sim.config import SimulatorConfig


def apply(
    resource: dict[str, Any], resource_type: str, config: SimulatorConfig
) -> dict[str, Any]:
    if resource_type == "Observation":
        resource = _add_epic_local_code(resource, config)
    if resource_type == "Patient":
        resource = _add_gender_identity_extension(resource, config)
    if resource_type == "MedicationRequest":
        resource = _add_medication_category(resource, config)
    return resource


def _add_epic_local_code(
    resource: dict[str, Any], config: SimulatorConfig
) -> dict[str, Any]:
    if not config.observation_include_epic_local_code:
        return resource
    code = resource.get("code")
    if not isinstance(code, dict):
        return resource
    codings = list(code.get("coding") or [])
    if any(
        isinstance(c, dict) and c.get("system") == config.epic_local_code_system
        for c in codings
    ):
        return resource
    loinc = next(
        (c for c in codings if isinstance(c, dict) and c.get("system") == "http://loinc.org"),
        None,
    )
    if loinc is None:
        return resource
    codings.append(
        {
            "system": config.epic_local_code_system,
            "code": f"EPIC-{loinc.get('code', 'UNKNOWN')}",
            "display": loinc.get("display"),
        }
    )
    return {**resource, "code": {**code, "coding": codings}}


def _add_gender_identity_extension(
    resource: dict[str, Any], config: SimulatorConfig
) -> dict[str, Any]:
    if not config.patient_gender_identity_extension:
        return resource
    existing = resource.get("extension") or []
    if any(
        isinstance(e, dict) and e.get("url") == config.gender_identity_extension_url
        for e in existing
    ):
        return resource
    gender = resource.get("gender")
    if not gender:
        return resource
    new_ext = list(existing) + [
        {
            "url": config.gender_identity_extension_url,
            "valueCodeableConcept": {"text": gender},
        }
    ]
    return {**resource, "extension": new_ext}


def _add_medication_category(
    resource: dict[str, Any], config: SimulatorConfig
) -> dict[str, Any]:
    category_code = config.medication_request_epic_category
    if not category_code:
        return resource
    existing = resource.get("category") or []
    if any(
        isinstance(c, dict)
        and any(
            isinstance(coding, dict) and coding.get("code") == category_code
            for coding in (c.get("coding") or [])
        )
        for c in existing
    ):
        return resource
    # Nominative reference to publicly documented Epic FHIR profile URI; see docs/EPIC_QUIRKS.md Q34.
    new_cat = list(existing) + [
        {
            "coding": [
                {
                    "system": "http://open.epic.com/FHIR/StructureDefinition/medication-request-category",
                    "code": category_code,
                }
            ]
        }
    ]
    return {**resource, "category": new_cat}
