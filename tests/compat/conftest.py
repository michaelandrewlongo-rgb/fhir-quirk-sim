"""
Re-export FixtureFhirClient from the epic_sim package so the Phase 1 HTTP
surface and the contract tests share a single replay engine.
"""
from pathlib import Path

import pytest

from epic_sim.fixtures import FixtureFhirClient, load_epic_fixture


EPIC_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "epic"


@pytest.fixture
def epic_fixture_client() -> FixtureFhirClient:
    return FixtureFhirClient(
        search_bundles={
            "Observation": load_epic_fixture("observations_labs_bundle.json"),
            "DocumentReference": load_epic_fixture("document_reference_bundle.json"),
        },
        binary_resources={
            "epic-note-001": load_epic_fixture("binary_note_success.json"),
        },
    )


__all__ = ["FixtureFhirClient", "load_epic_fixture", "EPIC_FIXTURE_DIR", "epic_fixture_client"]
