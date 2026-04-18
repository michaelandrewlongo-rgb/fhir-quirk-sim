"""Unit tests for the record-mode normalizer."""
from epic_sim.record.normalize import normalize_bundle, normalize_binary


class TestNormalizeBundle:
    def test_strips_bundle_id_and_timestamp(self):
        bundle = {
            "resourceType": "Bundle",
            "id": "sess-abc-123",
            "timestamp": "2026-04-17T12:00:00Z",
            "type": "searchset",
            "entry": [],
        }
        out = normalize_bundle(bundle)
        assert "id" not in out
        assert "timestamp" not in out
        assert out["type"] == "searchset"

    def test_replaces_session_scoped_next_link(self):
        bundle = {
            "resourceType": "Bundle",
            "type": "searchset",
            "link": [
                {"relation": "self", "url": "https://epic.example/Observation?..."},
                {"relation": "next", "url": "https://epic.example/Observation?session=abc"},
            ],
            "entry": [],
        }
        out = normalize_bundle(bundle)
        link_by_rel = {link["relation"]: link["url"] for link in out["link"]}
        assert link_by_rel["self"] == "__REPLAY_SELF__"
        assert link_by_rel["next"] == "__REPLAY_CURSOR__"

    def test_strips_resource_meta_lastupdated(self):
        bundle = {
            "resourceType": "Bundle",
            "type": "searchset",
            "entry": [
                {
                    "fullUrl": "https://epic.example/Observation/obs-1",
                    "resource": {
                        "resourceType": "Observation",
                        "id": "obs-1",
                        "meta": {
                            "versionId": "5",
                            "lastUpdated": "2026-04-17T00:00:00Z",
                            "profile": ["http://hl7.org/fhir/us/core/StructureDefinition/us-core-observation-lab"],
                        },
                    },
                }
            ],
        }
        out = normalize_bundle(bundle)
        resource = out["entry"][0]["resource"]
        assert "lastUpdated" not in resource["meta"]
        assert "versionId" not in resource["meta"]
        # Non-volatile meta preserved.
        assert resource["meta"]["profile"]
        # fullUrl normalized to a relative resourceType/id form.
        assert out["entry"][0]["fullUrl"] == "Observation/obs-1"

    def test_idempotent(self):
        bundle = {
            "resourceType": "Bundle",
            "id": "x",
            "type": "searchset",
            "entry": [
                {
                    "fullUrl": "Observation/obs-1",
                    "resource": {
                        "resourceType": "Observation",
                        "id": "obs-1",
                    },
                }
            ],
        }
        once = normalize_bundle(bundle)
        twice = normalize_bundle(once)
        assert once == twice


class TestNormalizeBinary:
    def test_strips_volatile_meta(self):
        binary = {
            "resourceType": "Binary",
            "id": "bin-1",
            "contentType": "text/html",
            "data": "PHA+aGVsbG88L3A+",
            "meta": {"lastUpdated": "2026-04-17T00:00:00Z", "versionId": "2"},
        }
        out = normalize_binary(binary)
        assert "meta" not in out
        assert out["data"] == "PHA+aGVsbG88L3A+"
