"""
Normalize captured Epic responses so replay is deterministic.

Strips volatile fields (timestamps, session-scoped next-page URLs, request IDs)
while preserving Epic-specific shape (opaque IDs, OIDs, extension URLs, missing
meta.lastUpdated). Idempotent: re-normalizing a normalized resource is a no-op.
"""
from copy import deepcopy
from typing import Any


_VOLATILE_META_KEYS = {"lastUpdated", "versionId"}


def normalize_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of bundle with volatile fields stripped from each entry."""
    out = deepcopy(bundle)
    out.pop("id", None)
    out.pop("timestamp", None)
    # Preserve search link relations but drop the opaque session cursor in next/prev
    # links — these are Epic-session-scoped and won't work on replay.
    kept_links = []
    for link in out.get("link", []):
        if not isinstance(link, dict):
            continue
        relation = link.get("relation")
        if relation in {"next", "previous", "prev"}:
            kept_links.append({"relation": relation, "url": "__REPLAY_CURSOR__"})
        elif relation == "self":
            kept_links.append({"relation": "self", "url": "__REPLAY_SELF__"})
        else:
            kept_links.append(link)
    if kept_links:
        out["link"] = kept_links
    for entry in out.get("entry", []):
        if isinstance(entry, dict) and "resource" in entry:
            entry["resource"] = _normalize_resource(entry["resource"])
            # fullUrl contains the server host; normalize to a relative form.
            if "fullUrl" in entry and isinstance(entry["fullUrl"], str):
                rid = entry["resource"].get("id", "unknown")
                rt = entry["resource"].get("resourceType", "Unknown")
                entry["fullUrl"] = f"{rt}/{rid}"
    return out


def normalize_binary(binary: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(binary)
    if "meta" in out and isinstance(out["meta"], dict):
        for k in _VOLATILE_META_KEYS:
            out["meta"].pop(k, None)
        if not out["meta"]:
            out.pop("meta")
    return out


def _normalize_resource(resource: dict[str, Any]) -> dict[str, Any]:
    meta = resource.get("meta")
    if isinstance(meta, dict):
        for k in _VOLATILE_META_KEYS:
            meta.pop(k, None)
        if not meta:
            resource.pop("meta", None)
    return resource
