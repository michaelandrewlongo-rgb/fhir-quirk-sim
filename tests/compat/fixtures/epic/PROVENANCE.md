# Fixture provenance

All fixtures in this directory are hand-authored synthetic data. None are
copied, normalized, or derived from Epic sandbox captures. This table lists
the shape each fixture is modeled after and the public references that
justify the code systems and structural choices used.

| Fixture | Resource shape | Derived from (public references) | Related quirks |
|---|---|---|---|
| `observations_labs_bundle.json` | FHIR R4 `Bundle` (searchset) of `Observation` | FHIR R4 Observation spec; LOINC code system; Epic-local code pattern described in `docs/EPIC_QUIRKS.md` Q32 | Q15, Q32 |
| `document_reference_bundle.json` | FHIR R4 `Bundle` of `DocumentReference` with attached `Binary` URLs | FHIR R4 DocumentReference spec; Epic clinical-note dereference pattern documented in `docs/EPIC_QUIRKS.md` Q24 | Q24 |
| `binary_note_success.json` | FHIR R4 `Binary` with base64 HTML | FHIR R4 Binary spec | Q24 |
| `binary_forbidden_operation_outcome.json` | FHIR R4 `OperationOutcome` for Binary 403 | FHIR R4 OperationOutcome spec; HL7 `issue-severity` and `issue-type` value sets | Q24, Q28 |
| `unsupported_search_operation_outcome.json` | FHIR R4 `OperationOutcome` for unsupported search | FHIR R4 OperationOutcome spec; Epic behavior documented in `docs/EPIC_QUIRKS.md` Q15 | Q15 |
| `smart_launch_context.json` | SMART EHR launch context stub | HL7 SMART App Launch 2.x specification | Q1 |

## Synthetic identifiers

| Identifier | Where used | Purpose |
|---|---|---|
| `urn:oid:1.2.840.114350.1.13.999.234` | `observations_labs_bundle.json` | Illustrative synthetic Epic-local OID. The `.999.` arc is a deliberate sentinel — not a real Epic OID. |
| `epic-patient-001`, `epic-obs-*-001`, `epic-note-001`, `epic-encounter-001`, `epic-user-001` | all fixtures | Placeholder resource IDs. |
| `fhir.epic.example.com` | `fullUrl` and `link.url` fields | Placeholder host under `example.com` (RFC 2606). |
| `synthetic-token` | `smart_launch_context.json` | Placeholder access token. |

## Updating fixtures

Do not paste sandbox bytes into these files. If fixture shapes need to track
real Epic behavior, capture into `private/captures/` using
`scripts/record_sandbox.py --acknowledge-private ...` and use
`scripts/calibrate_fixtures.py` to diff structure; then rewrite the synthetic
fixtures by hand.
