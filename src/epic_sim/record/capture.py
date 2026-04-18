"""
RecordingFhirAdapter — wraps GenericFhirAdapter and tees every response to disk.

Lets the user hit Epic's public sandbox (or a customer TST) once, capture the
real byte-shape of responses, and never have to touch that environment again
during iteration. The captured fixtures are then served by FixtureFhirClient
through the HTTP surface.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fhir_proxy.fhir_client.generic_adapter import GenericFhirAdapter
from epic_sim.record.normalize import normalize_bundle, normalize_binary


class RecordingFhirAdapter(GenericFhirAdapter):
    """GenericFhirAdapter that writes every successful response to a capture dir."""

    def __init__(
        self,
        base_url: str,
        capture_root: Path,
        tag: str,
        auth_token: str | None = None,
    ):
        super().__init__(base_url=base_url, auth_token=auth_token)
        self.capture_dir = Path(capture_root) / tag
        self.capture_dir.mkdir(parents=True, exist_ok=True)
        self.tag = tag

    async def search(
        self,
        resource_type: str,
        patient_id: str,
        params: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        resources = await super().search(resource_type, patient_id, params)
        # Reconstruct a bundle-shaped capture from the flattened list.
        pseudo_bundle = {
            "resourceType": "Bundle",
            "type": "searchset",
            "total": len(resources),
            "entry": [{"resource": r} for r in resources],
        }
        self._write(
            category="search",
            resource_type=resource_type,
            key=self._search_key(resource_type, patient_id, params),
            payload=normalize_bundle(pseudo_bundle),
        )
        return resources

    async def read(self, resource_type: str, resource_id: str) -> dict[str, Any] | None:
        resource = await super().read(resource_type, resource_id)
        if resource is not None:
            self._write(
                category="read",
                resource_type=resource_type,
                key=resource_id,
                payload=resource,
            )
        return resource

    async def read_binary(self, url: str) -> tuple[str, str] | None:
        result = await super().read_binary(url)
        if result is not None:
            binary_id = url.rstrip("/").split("/")[-1]
            decoded, content_type = result
            import base64
            payload = {
                "resourceType": "Binary",
                "id": binary_id,
                "contentType": content_type,
                "data": base64.b64encode(decoded.encode("utf-8")).decode("ascii"),
            }
            self._write(
                category="binary",
                resource_type="Binary",
                key=binary_id,
                payload=normalize_binary(payload),
            )
        return result

    @staticmethod
    def _search_key(
        resource_type: str, patient_id: str, params: dict[str, str] | None
    ) -> str:
        """Deterministic filename token from the search inputs."""
        params_part = json.dumps(params or {}, sort_keys=True)
        h = hashlib.sha256(
            f"{resource_type}|{patient_id}|{params_part}".encode()
        ).hexdigest()[:10]
        return f"patient_{patient_id}_{h}"

    def _write(self, category: str, resource_type: str, key: str, payload: dict) -> None:
        target_dir = self.capture_dir / category / resource_type
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{key}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
