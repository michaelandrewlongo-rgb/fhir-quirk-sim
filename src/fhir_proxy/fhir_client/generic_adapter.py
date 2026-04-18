import base64
from typing import Any
import httpx
from fhir_proxy.fhir_client.base import FhirClient


class GenericFhirAdapter(FhirClient):
    def __init__(self, base_url: str, auth_token: str | None = None):
        self.base_url = base_url.rstrip("/")
        headers = {"Accept": "application/fhir+json"}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        self.client = httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=30.0)

    async def search(self, resource_type: str, patient_id: str, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
        search_params = {"patient": patient_id}
        if params:
            search_params.update(params)
        resources = []
        url = f"/{resource_type}"
        while url:
            resp = await self.client.get(url, params=search_params)
            resp.raise_for_status()
            bundle = resp.json()
            for entry in bundle.get("entry", []):
                if "resource" in entry:
                    resources.append(entry["resource"])
            url = None
            search_params = None
            for link in bundle.get("link", []):
                if link.get("relation") == "next":
                    url = link["url"]
                    break
        return resources

    async def read(self, resource_type: str, resource_id: str) -> dict[str, Any] | None:
        resp = await self.client.get(f"/{resource_type}/{resource_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    async def read_binary(self, url: str) -> tuple[str, str] | None:
        """
        Fetch a Binary resource. url may be relative or absolute.

        Returns (decoded_text, content_type) or None if not found.
        """
        if url.startswith("http://") or url.startswith("https://"):
            resp = await self.client.get(url)
        else:
            path = url if url.startswith("/") else f"/{url}"
            resp = await self.client.get(path)

        if resp.status_code == 404:
            return None
        resp.raise_for_status()

        binary = resp.json()
        content_type = binary.get("contentType", "application/octet-stream")
        encoded_data = binary.get("data", "")
        if not encoded_data:
            return None

        decoded_bytes = base64.b64decode(encoded_data)
        decoded_text = decoded_bytes.decode("utf-8", errors="replace")
        return decoded_text, content_type

    async def close(self):
        await self.client.aclose()
