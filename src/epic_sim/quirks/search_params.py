"""
Search-parameter quirks.

- unsupported_param_behavior=reject → OperationOutcome 400 for _since on non-bulk
  paths, for `_include:iterate`, `_revinclude`, and any param not in the allowlist.
- post_filter_enabled → discard the tail of the page to simulate Epic's
  post-filter pagination underfill.
- max_page_size → truncate beyond the cap. Epic caps pages below what clients
  request.
"""
from __future__ import annotations

import hashlib
from typing import Any

from epic_sim.config import SimulatorConfig
from epic_sim.errors import FhirHTTPError

# Allowlist of params the fixture layer actually understands. Anything else is
# either silently dropped or rejected depending on config.
_BASE_SUPPORTED = {"patient", "subject", "code", "category", "date", "status", "_count"}


def reject_unsupported_params(
    resource_type: str, params: dict[str, str], config: SimulatorConfig
) -> None:
    for name in params:
        if name == "_since" and not config.bulk_since_supported:
            if config.unsupported_param_behavior == "reject":
                raise FhirHTTPError(
                    400, "not-supported", "_since is not supported outside bulk export"
                )
            continue
        if name == "_include:iterate" and not config.include_iterate_supported:
            if config.unsupported_param_behavior == "reject":
                raise FhirHTTPError(
                    400, "not-supported", "_include:iterate is not supported"
                )
            continue
        if name == "_revinclude" and not config.revinclude_supported:
            if config.unsupported_param_behavior == "reject":
                raise FhirHTTPError(400, "not-supported", "_revinclude is not supported")
            continue


def drop_unsupported_modifiers(
    params: dict[str, str],
    config: SimulatorConfig,
    resources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Silently drop unsupported params when behavior=ignore — resources pass through unchanged."""
    return resources


def post_filter_discard(
    resources: list[dict[str, Any]], config: SimulatorConfig
) -> list[dict[str, Any]]:
    if not config.post_filter_enabled or not resources:
        return resources
    rate = max(0.0, min(1.0, config.post_filter_discard_rate))
    keep = max(1, int(round(len(resources) * (1.0 - rate))))
    return resources[:keep]


def cap_page_size(
    resources: list[dict[str, Any]], config: SimulatorConfig
) -> list[dict[str, Any]]:
    cap = config.max_page_size
    if cap and len(resources) > cap:
        return resources[:cap]
    return resources
