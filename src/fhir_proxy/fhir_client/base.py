from abc import ABC, abstractmethod
from typing import Any


class FhirClient(ABC):
    @abstractmethod
    async def search(self, resource_type: str, patient_id: str, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
        """Search for FHIR resources by type and patient."""

    @abstractmethod
    async def read(self, resource_type: str, resource_id: str) -> dict[str, Any] | None:
        """Read a single FHIR resource by ID."""

    @abstractmethod
    async def read_binary(self, url: str) -> tuple[str, str] | None:
        """
        Fetch a Binary resource and return (decoded_content, content_type).

        url may be relative ('Binary/abc123') or absolute ('https://...').
        Returns None if the resource is not found or has no data.
        """
