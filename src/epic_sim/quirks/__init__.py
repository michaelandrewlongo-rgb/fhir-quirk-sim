"""
Quirk injection pipeline.

`apply_search_quirks` transforms a list of resources after `FixtureFhirClient`
returns them but before the HTTP layer wraps them in a Bundle. `apply_read_quirks`
transforms a single resource for read endpoints. Each quirk family reads one or
two config fields — keep modules isolated so they can be toggled independently
from `SimulatorConfig`.
"""
from __future__ import annotations

from typing import Any

from epic_sim.config import SimulatorConfig
from epic_sim.errors import FhirHTTPError
from epic_sim.quirks import (
    errors as errors_q,
    extensions as extensions_q,
    references as references_q,
    resource_shape as resource_shape_q,
    search_params as search_params_q,
)


def apply_search_quirks(
    resource_type: str,
    resources: list[dict[str, Any]],
    params: dict[str, str],
    config: SimulatorConfig,
) -> list[dict[str, Any]]:
    """Transform a search result list. Raises FhirHTTPError for hard failures."""
    search_params_q.reject_unsupported_params(resource_type, params, config)
    resources = search_params_q.drop_unsupported_modifiers(params, config, resources)
    resources = [_apply_resource_shape(r, resource_type, config) for r in resources]
    resources = [references_q.maybe_inline_docref(r, config) for r in resources]
    resources = [extensions_q.apply(r, resource_type, config) for r in resources]
    resources = resource_shape_q.filter_careteam(resources, resource_type, config)
    resources = resource_shape_q.inject_condition_access_errors(
        resources, resource_type, config
    )
    resources = search_params_q.post_filter_discard(resources, config)
    resources = search_params_q.cap_page_size(resources, config)
    return resources


def apply_read_quirks(
    resource_type: str,
    resource: dict[str, Any],
    config: SimulatorConfig,
) -> dict[str, Any]:
    resource = _apply_resource_shape(resource, resource_type, config)
    resource = references_q.maybe_inline_docref(resource, config)
    resource = extensions_q.apply(resource, resource_type, config)
    return resource


def check_binary_access(binary_id: str, config: SimulatorConfig) -> None:
    """Raises FhirHTTPError(403) deterministically based on binary id + rate."""
    references_q.maybe_block_binary(binary_id, config)


def check_patient_access(patient_id: str | None, config: SimulatorConfig) -> None:
    if patient_id is None:
        return
    errors_q.maybe_block_vip(patient_id, config)


def _apply_resource_shape(
    resource: dict[str, Any], resource_type: str, config: SimulatorConfig
) -> dict[str, Any]:
    resource = resource_shape_q.strip_meta_last_updated(resource, config)
    resource = resource_shape_q.strip_has_member(resource, resource_type, config)
    resource = resource_shape_q.apply_mrn_type_text(resource, resource_type, config)
    return resource


__all__ = [
    "apply_search_quirks",
    "apply_read_quirks",
    "check_binary_access",
    "check_patient_access",
]
