"""
Fixture-backed FhirClient for the Epic simulator.

Lifted from tests/compat/conftest.py so it can back the HTTP surface as well as
the in-process contract tests. The test conftest re-exports from this module.

All fixtures under tests/compat/fixtures/epic/ are hand-authored synthetic
data. Per-fixture provenance lives in sibling `<name>.provenance.json` files
rather than inside the fixture bytes, so loaders never need to strip a
provenance key before passing bytes downstream. See
tests/compat/fixtures/epic/PROVENANCE.md.
"""
import base64
import json
from pathlib import Path
from typing import Any

from fhir_proxy.fhir_client.base import FhirClient


_DEFAULT_FIXTURE_ROOT = (
    Path(__file__).resolve().parent.parent.parent / "tests" / "compat" / "fixtures" / "epic"
)


def load_epic_fixture(name: str, root: Path | None = None) -> dict[str, Any]:
    fixture_dir = root if root is not None else _DEFAULT_FIXTURE_ROOT
    with open(fixture_dir / name, "r", encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def _bundle_resources(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        entry["resource"]
        for entry in bundle.get("entry", [])
        if isinstance(entry, dict) and "resource" in entry
    ]


def _coding_codes(resource: dict[str, Any]) -> set[str]:
    codeable = resource.get("code", {})
    return {
        coding.get("code")
        for coding in codeable.get("coding", [])
        if isinstance(coding, dict) and coding.get("code")
    }


def _category_codes(resource: dict[str, Any]) -> set[str]:
    categories = resource.get("category", [])
    codes: set[str] = set()
    for category in categories:
        for coding in category.get("coding", []):
            if isinstance(coding, dict) and coding.get("code"):
                codes.add(coding["code"])
    return codes


def _operation_outcome_message(outcome: dict[str, Any]) -> str:
    diagnostics = [
        issue.get("diagnostics") or issue.get("code")
        for issue in outcome.get("issue", [])
        if isinstance(issue, dict)
    ]
    return "; ".join(str(item) for item in diagnostics if item) or "FHIR OperationOutcome"


class FixtureFhirClient(FhirClient):
    """Replay a narrow set of Epic-shaped FHIR fixtures through the FhirClient API."""

    def __init__(
        self,
        search_bundles: dict[str, dict[str, Any]],
        binary_resources: dict[str, dict[str, Any]],
        unsupported_searches: set[tuple[str, str]] | None = None,
        forbidden_binaries: set[str] | None = None,
        fixture_root: Path | None = None,
    ) -> None:
        self.search_bundles = search_bundles
        self.binary_resources = binary_resources
        self.unsupported_searches = unsupported_searches or set()
        self.forbidden_binaries = forbidden_binaries or set()
        self.fixture_root = fixture_root if fixture_root is not None else _DEFAULT_FIXTURE_ROOT
        self.search_calls: list[tuple[str, str, dict[str, str] | None]] = []
        self.binary_calls: list[str] = []

    async def search(
        self,
        resource_type: str,
        patient_id: str,
        params: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        self.search_calls.append((resource_type, patient_id, params))
        for param_name in params or {}:
            if (resource_type, param_name) in self.unsupported_searches:
                outcome = load_epic_fixture(
                    "unsupported_search_operation_outcome.json", root=self.fixture_root
                )
                raise RuntimeError(_operation_outcome_message(outcome))

        bundle = self.search_bundles.get(resource_type)
        if bundle is None:
            return []

        resources = _bundle_resources(bundle)
        codes = set((params or {}).get("code", "").split(",")) - {""}
        if codes:
            resources = [resource for resource in resources if _coding_codes(resource) & codes]

        category = (params or {}).get("category")
        if category:
            resources = [
                resource for resource in resources if category in _category_codes(resource)
            ]

        return resources

    async def read(self, resource_type: str, resource_id: str) -> dict[str, Any] | None:
        if resource_type == "Binary":
            return self.binary_resources.get(resource_id)
        bundle = self.search_bundles.get(resource_type)
        if bundle is None:
            return None
        for resource in _bundle_resources(bundle):
            if resource.get("id") == resource_id:
                return resource
        return None

    async def read_binary(self, url: str) -> tuple[str, str] | None:
        self.binary_calls.append(url)
        binary_id = url.rstrip("/").split("/")[-1]
        if binary_id in self.forbidden_binaries:
            outcome = load_epic_fixture(
                "binary_forbidden_operation_outcome.json", root=self.fixture_root
            )
            raise RuntimeError(_operation_outcome_message(outcome))

        binary = self.binary_resources.get(binary_id)
        if binary is None:
            return None

        encoded = binary.get("data")
        if not encoded:
            return None
        decoded = base64.b64decode(encoded).decode("utf-8", errors="replace")
        return decoded, binary.get("contentType", "application/octet-stream")


def load_default_client(fixture_root: Path | None = None) -> FixtureFhirClient:
    """Load the default fixture set shipped with the repo."""
    root = fixture_root if fixture_root is not None else _DEFAULT_FIXTURE_ROOT
    return FixtureFhirClient(
        search_bundles={
            "Observation": load_epic_fixture("observations_labs_bundle.json", root=root),
            "DocumentReference": load_epic_fixture("document_reference_bundle.json", root=root),
        },
        binary_resources={
            "epic-note-001": load_epic_fixture("binary_note_success.json", root=root),
        },
        fixture_root=root,
    )
