"""Unit tests for quirk family modules. Directly exercise the quirk functions."""
from __future__ import annotations

import pytest

from epic_sim.config import SimulatorConfig
from epic_sim.errors import FhirHTTPError
from epic_sim.quirks import (
    errors as errors_q,
    extensions as extensions_q,
    references as references_q,
    resource_shape as resource_shape_q,
    search_params as search_params_q,
)


# --- search_params ---------------------------------------------------------

def test_rejects_since_when_bulk_disabled():
    cfg = SimulatorConfig()
    with pytest.raises(FhirHTTPError) as e:
        search_params_q.reject_unsupported_params("Observation", {"_since": "2024-01-01"}, cfg)
    assert e.value.status_code == 400


def test_rejects_include_iterate():
    cfg = SimulatorConfig()
    with pytest.raises(FhirHTTPError):
        search_params_q.reject_unsupported_params(
            "Observation", {"_include:iterate": "Observation:patient"}, cfg
        )


def test_rejects_revinclude():
    cfg = SimulatorConfig()
    with pytest.raises(FhirHTTPError):
        search_params_q.reject_unsupported_params(
            "Observation", {"_revinclude": "Provenance:target"}, cfg
        )


def test_ignore_mode_does_not_raise():
    cfg = SimulatorConfig(unsupported_param_behavior="ignore")
    search_params_q.reject_unsupported_params("Observation", {"_since": "2024"}, cfg)


def test_post_filter_discards_tail():
    cfg = SimulatorConfig(post_filter_enabled=True, post_filter_discard_rate=0.5)
    resources = [{"id": str(i)} for i in range(10)]
    out = search_params_q.post_filter_discard(resources, cfg)
    assert len(out) == 5


def test_post_filter_disabled_keeps_all():
    cfg = SimulatorConfig(post_filter_enabled=False)
    resources = [{"id": str(i)} for i in range(10)]
    assert search_params_q.post_filter_discard(resources, cfg) == resources


def test_cap_page_size_truncates():
    cfg = SimulatorConfig(max_page_size=3)
    out = search_params_q.cap_page_size([{"id": str(i)} for i in range(10)], cfg)
    assert len(out) == 3


# --- resource_shape --------------------------------------------------------

def test_strip_meta_last_updated():
    cfg = SimulatorConfig(populate_meta_last_updated=False)
    r = {"id": "x", "meta": {"lastUpdated": "2024-01-01T00:00:00Z", "versionId": "1"}}
    out = resource_shape_q.strip_meta_last_updated(r, cfg)
    assert "lastUpdated" not in out["meta"]
    assert out["meta"]["versionId"] == "1"


def test_keep_meta_when_enabled():
    cfg = SimulatorConfig(populate_meta_last_updated=True)
    r = {"meta": {"lastUpdated": "2024-01-01T00:00:00Z"}}
    assert resource_shape_q.strip_meta_last_updated(r, cfg) == r


def test_strip_has_member_on_observation():
    cfg = SimulatorConfig(observation_include_has_member=False)
    r = {"resourceType": "Observation", "hasMember": [{"reference": "Observation/1"}]}
    out = resource_shape_q.strip_has_member(r, "Observation", cfg)
    assert "hasMember" not in out


def test_mrn_type_text_applied():
    cfg = SimulatorConfig(mrn_type_text_value="MRN")
    r = {
        "identifier": [
            {"type": {"coding": [{"code": "MR"}]}, "value": "123"},
            {"type": {"coding": [{"code": "SSN"}]}, "value": "456"},
        ]
    }
    out = resource_shape_q.apply_mrn_type_text(r, "Patient", cfg)
    assert out["identifier"][0]["type"]["text"] == "MRN"
    assert "text" not in out["identifier"][1]["type"]


def test_filter_careteam_inpatient():
    cfg = SimulatorConfig(careteam_excludes_inpatient=True)
    resources = [
        {"id": "out", "category": [{"coding": [{"code": "ambulatory"}]}]},
        {"id": "in", "category": [{"coding": [{"code": "inpatient"}]}]},
    ]
    out = resource_shape_q.filter_careteam(resources, "CareTeam", cfg)
    ids = [r["id"] for r in out]
    assert ids == ["out"]


def test_condition_access_errors_injected():
    cfg = SimulatorConfig(condition_bulk_inject_access_errors=True)
    resources = [
        {"id": "c1", "category": [{"coding": [{"code": "problem-list"}]}]},
        {"id": "c2", "category": [{"coding": [{"code": "dental-finding"}]}]},
    ]
    out = resource_shape_q.inject_condition_access_errors(resources, "Condition", cfg)
    assert out[0]["id"] == "c1"
    assert out[1]["resourceType"] == "OperationOutcome"
    assert out[1]["issue"][0]["code"] == "forbidden"


# --- references ------------------------------------------------------------

def test_binary_403_deterministic_blocks_when_rate_100():
    cfg = SimulatorConfig(binary_403_rate=1.0)
    with pytest.raises(FhirHTTPError) as e:
        references_q.maybe_block_binary("any-id", cfg)
    assert e.value.status_code == 403


def test_binary_403_rate_zero_never_blocks():
    cfg = SimulatorConfig(binary_403_rate=0.0)
    references_q.maybe_block_binary("any-id", cfg)


def test_binary_403_deterministic_same_id_same_result():
    cfg = SimulatorConfig(binary_403_rate=0.5)
    results = []
    for _ in range(3):
        try:
            references_q.maybe_block_binary("stable-id", cfg)
            results.append("ok")
        except FhirHTTPError:
            results.append("403")
    assert len(set(results)) == 1  # same every time


def test_docref_inline_data_stripped():
    cfg = SimulatorConfig(docref_inline_data=False)
    r = {
        "resourceType": "DocumentReference",
        "content": [{"attachment": {"data": "BASE64", "url": "Binary/xyz"}}],
    }
    out = references_q.maybe_inline_docref(r, cfg)
    assert "data" not in out["content"][0]["attachment"]
    assert out["content"][0]["attachment"]["url"] == "Binary/xyz"


def test_docref_inline_data_kept():
    cfg = SimulatorConfig(docref_inline_data=True)
    r = {
        "resourceType": "DocumentReference",
        "content": [{"attachment": {"data": "BASE64"}}],
    }
    assert references_q.maybe_inline_docref(r, cfg) == r


# --- errors ----------------------------------------------------------------

def test_vip_patient_blocked():
    cfg = SimulatorConfig(vip_patient_ids=["vip-1"])
    with pytest.raises(FhirHTTPError) as e:
        errors_q.maybe_block_vip("vip-1", cfg)
    assert e.value.status_code == 403


def test_vip_patient_not_blocked_when_not_listed():
    cfg = SimulatorConfig(vip_patient_ids=["vip-1"])
    errors_q.maybe_block_vip("normal-patient", cfg)


# --- extensions ------------------------------------------------------------

def test_epic_local_code_added_to_observation():
    cfg = SimulatorConfig(observation_include_epic_local_code=True)
    r = {
        "resourceType": "Observation",
        "code": {"coding": [{"system": "http://loinc.org", "code": "2339-0"}]},
    }
    out = extensions_q.apply(r, "Observation", cfg)
    systems = [c["system"] for c in out["code"]["coding"]]
    assert cfg.epic_local_code_system in systems


def test_epic_local_code_idempotent():
    cfg = SimulatorConfig()
    r = {
        "resourceType": "Observation",
        "code": {"coding": [{"system": "http://loinc.org", "code": "2339-0"}]},
    }
    once = extensions_q.apply(r, "Observation", cfg)
    twice = extensions_q.apply(once, "Observation", cfg)
    assert once == twice


def test_gender_identity_extension_added():
    cfg = SimulatorConfig(patient_gender_identity_extension=True)
    r = {"resourceType": "Patient", "gender": "female"}
    out = extensions_q.apply(r, "Patient", cfg)
    urls = [e["url"] for e in out["extension"]]
    assert cfg.gender_identity_extension_url in urls


def test_medication_category_added():
    cfg = SimulatorConfig()
    r = {"resourceType": "MedicationRequest", "status": "active"}
    out = extensions_q.apply(r, "MedicationRequest", cfg)
    categories = out["category"]
    assert any(
        coding.get("code") == cfg.medication_request_epic_category
        for cat in categories
        for coding in cat.get("coding", [])
    )
