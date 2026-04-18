"""
SimulatorConfig — runtime knobs for every Epic quirk in docs/EPIC_QUIRKS.md.

This Phase 2 module is pure plumbing: no behavior change yet. Later phases read
individual fields to drive auth flow, quirk injection, rate limiting, etc.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class SimulatorConfig(BaseModel):
    # === Auth / SMART ===
    backend_services_jwt_required: bool = True
    auth_code_format: Literal["opaque", "jwt"] = "jwt"
    online_access_returns_offline: bool = True
    fhir_user_in_id_token: bool = True
    omit_introspection_endpoint: bool = True
    omit_revocation_endpoint: bool = True
    omit_registration_endpoint: bool = True
    mfa_challenge_enabled: bool = False
    jwt_jti_max_length: int = 151
    jwt_exp_max_minutes: int = 5
    jwt_jti_replay_check: bool = True
    jwt_aud_allowlist: list[str] = Field(default_factory=list)
    config_propagation_delay_seconds: int = 0

    # === Search Params ===
    post_filter_enabled: bool = True
    post_filter_discard_rate: float = 0.3
    unsupported_param_behavior: Literal["reject", "ignore"] = "reject"
    mrn_oid_system: str = "urn:oid:1.2.840.114350.1.13.0.1.7.5.737384.14"
    bulk_since_supported: bool = False
    include_iterate_supported: bool = False
    revinclude_supported: bool = False
    max_page_size: int = 100

    # === Resource Shape ===
    populate_meta_last_updated: bool = False
    fhir_id_format: Literal["opaque_b64", "uuid"] = "opaque_b64"
    careteam_excludes_inpatient: bool = True
    consent_returns_full_document: bool = False
    consent_patient_facing_allowed: bool = False
    condition_bulk_inject_access_errors: bool = True
    condition_inaccessible_subtypes: list[str] = Field(
        default_factory=lambda: ["dental-finding", "encounter-diagnosis-restricted"]
    )
    observation_hidden_in_dr_result: bool = True
    observation_include_has_member: bool = False
    mrn_type_text_value: str | None = "MRN"

    # === References & Dereferencing ===
    binary_403_rate: float = 0.0
    docref_inline_data: bool = False
    pagination_cursor_opaque: bool = True
    pagination_cursor_ttl_seconds: int = 300

    # === Errors & Status Codes ===
    vip_patient_ids: list[str] = Field(default_factory=list)
    btg_403_rate: float = 0.0
    cds_hooks_actions_hit_fhir: bool = False

    # === Rate Limits & Pagination ===
    bulk_request_window_hours: int = 24
    docref_daily_cap: int | None = None
    bulk_group_cooldown_hours: int = 24

    # === Extensions ===
    observation_include_epic_local_code: bool = True
    epic_local_code_system: str = "urn:oid:1.2.840.114350.1.13.5.1.7.2.707679"
    patient_gender_identity_extension: bool = True
    gender_identity_extension_url: str = (
        "http://open.epic.com/FHIR/StructureDefinition/patient-gender-identity"
    )
    medication_request_epic_category: str = "community"

    # === Bulk Data ===
    bulk_group_ids: list[str] = Field(default_factory=lambda: ["group-test-001"])
    bulk_oversized_id_rate: float = 0.0
    bulk_oversized_id_length: int = 80
    bulk_polling_duration_seconds: int = 30
    bulk_x_progress_template: str = "{n} ids processed"

    # === Write-back ===
    observation_write_mapped_loincs: list[str] = Field(
        default_factory=lambda: ["8302-2", "8867-4", "59408-5", "29463-7", "8310-5"]
    )
    appointment_create_supported: bool = False
    appointment_find_op_supported: bool = True
    appointment_book_op_supported: bool = True
    encounter_create_supported: bool = False

    # === Versioning ===
    fhir_versions_active: list[str] = Field(default_factory=lambda: ["R4"])

    # === CDS Hooks ===
    cds_hooks_supported_hooks: list[str] = Field(default_factory=lambda: ["patient-view"])

    # === Sim-level plumbing (not an Epic quirk) ===
    auth_required: bool = False  # Phase 1 default: no auth. Flipped on in Phase 3.

    @classmethod
    def from_yaml(cls, path: str | Path) -> "SimulatorConfig":
        import yaml

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls.model_validate(data)

    @classmethod
    def from_env(cls, env_var: str = "EPIC_SIM_CONFIG") -> "SimulatorConfig":
        path = os.environ.get(env_var)
        if not path:
            return cls()
        return cls.from_yaml(path)
