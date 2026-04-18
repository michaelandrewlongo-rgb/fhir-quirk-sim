"""
Reference / dereferencing quirks.

- binary_403_rate → deterministically block Binary reads based on hash of id.
  Deterministic so CI is reproducible even when rate > 0.
- docref_inline_data=False → strip DocumentReference.content[].attachment.data,
  forcing the client to dereference the referenced Binary (Epic's behavior).
"""
from __future__ import annotations

import hashlib
from typing import Any

from epic_sim.config import SimulatorConfig
from epic_sim.errors import FhirHTTPError


def maybe_block_binary(binary_id: str, config: SimulatorConfig) -> None:
    rate = max(0.0, min(1.0, config.binary_403_rate))
    if rate <= 0.0:
        return
    digest = hashlib.sha256(binary_id.encode("utf-8")).digest()
    # Map first 2 bytes into [0, 1) — deterministic per binary id.
    score = int.from_bytes(digest[:2], "big") / 65535.0
    if score < rate:
        raise FhirHTTPError(
            403, "forbidden", f"Binary/{binary_id} blocked (sensitive document)"
        )


def maybe_inline_docref(
    resource: dict[str, Any], config: SimulatorConfig
) -> dict[str, Any]:
    if config.docref_inline_data:
        return resource
    if resource.get("resourceType") != "DocumentReference":
        return resource
    content = resource.get("content")
    if not isinstance(content, list):
        return resource
    changed = False
    new_content = []
    for item in content:
        if not isinstance(item, dict):
            new_content.append(item)
            continue
        attachment = item.get("attachment")
        if isinstance(attachment, dict) and "data" in attachment:
            new_att = {k: v for k, v in attachment.items() if k != "data"}
            new_content.append({**item, "attachment": new_att})
            changed = True
        else:
            new_content.append(item)
    if changed:
        resource = {**resource, "content": new_content}
    return resource
