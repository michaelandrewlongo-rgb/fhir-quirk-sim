"""
Resource-shape quirks — the mutations Epic applies to resource bodies.

- populate_meta_last_updated=False → strip meta.lastUpdated (Epic omits it)
- careteam_excludes_inpatient → drop CareTeam entries with inpatient category
- observation_include_has_member=False → strip hasMember from Observation
- mrn_type_text_value → Patient.identifier of type MR gets type.text = "MRN"
- condition_bulk_inject_access_errors → some Condition subtypes return as
  OperationOutcome-in-entry instead of the resource.
"""
from __future__ import annotations

from typing import Any

from epic_sim.config import SimulatorConfig

_INPATIENT_CATEGORY_CODES = {"inpatient", "LA", "longitudinal-admin"}


def strip_meta_last_updated(
    resource: dict[str, Any], config: SimulatorConfig
) -> dict[str, Any]:
    if config.populate_meta_last_updated:
        return resource
    meta = resource.get("meta")
    if isinstance(meta, dict) and "lastUpdated" in meta:
        meta = {k: v for k, v in meta.items() if k != "lastUpdated"}
        resource = {**resource, "meta": meta} if meta else {
            k: v for k, v in resource.items() if k != "meta"
        }
    return resource


def strip_has_member(
    resource: dict[str, Any], resource_type: str, config: SimulatorConfig
) -> dict[str, Any]:
    if resource_type != "Observation" or config.observation_include_has_member:
        return resource
    if "hasMember" in resource:
        resource = {k: v for k, v in resource.items() if k != "hasMember"}
    return resource


def apply_mrn_type_text(
    resource: dict[str, Any], resource_type: str, config: SimulatorConfig
) -> dict[str, Any]:
    if resource_type != "Patient" or not config.mrn_type_text_value:
        return resource
    identifiers = resource.get("identifier")
    if not isinstance(identifiers, list):
        return resource
    patched = []
    changed = False
    for ident in identifiers:
        if not isinstance(ident, dict):
            patched.append(ident)
            continue
        type_block = ident.get("type") or {}
        codings = type_block.get("coding") or []
        has_mr = any(
            isinstance(c, dict) and c.get("code") == "MR" for c in codings
        )
        if has_mr and type_block.get("text") != config.mrn_type_text_value:
            new_type = {**type_block, "text": config.mrn_type_text_value}
            patched.append({**ident, "type": new_type})
            changed = True
        else:
            patched.append(ident)
    if changed:
        resource = {**resource, "identifier": patched}
    return resource


def filter_careteam(
    resources: list[dict[str, Any]], resource_type: str, config: SimulatorConfig
) -> list[dict[str, Any]]:
    if resource_type != "CareTeam" or not config.careteam_excludes_inpatient:
        return resources
    out = []
    for r in resources:
        categories = r.get("category", []) or []
        inpatient = False
        for cat in categories:
            for coding in (cat.get("coding") or []) if isinstance(cat, dict) else []:
                if (
                    isinstance(coding, dict)
                    and coding.get("code") in _INPATIENT_CATEGORY_CODES
                ):
                    inpatient = True
                    break
            if inpatient:
                break
        if not inpatient:
            out.append(r)
    return out


def inject_condition_access_errors(
    resources: list[dict[str, Any]], resource_type: str, config: SimulatorConfig
) -> list[dict[str, Any]]:
    """Condition subtypes like dental-finding come back blocked in bulk reads."""
    if resource_type != "Condition" or not config.condition_bulk_inject_access_errors:
        return resources
    blocked = set(config.condition_inaccessible_subtypes)
    out = []
    for r in resources:
        categories = r.get("category", []) or []
        matched = False
        for cat in categories:
            for coding in (cat.get("coding") or []) if isinstance(cat, dict) else []:
                if isinstance(coding, dict) and coding.get("code") in blocked:
                    matched = True
                    break
            if matched:
                break
        if matched:
            out.append(
                {
                    "resourceType": "OperationOutcome",
                    "issue": [
                        {
                            "severity": "error",
                            "code": "forbidden",
                            "diagnostics": (
                                f"Condition/{r.get('id', 'unknown')} access blocked "
                                f"(subtype not available in bulk)"
                            ),
                        }
                    ],
                }
            )
        else:
            out.append(r)
    return out
