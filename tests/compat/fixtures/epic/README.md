# Epic-shaped fixtures

Every JSON file in this directory is **hand-authored synthetic data**. No bytes
originate from an Epic sandbox, customer environment, or any Epic-authored
source. Fixtures are shaped to match FHIR R4 responses observed from Epic
endpoints, so that client code can be exercised against the same structural
patterns without redistributing Epic-authored Materials.

## Rules

- Patient, encounter, and resource IDs are placeholders (`epic-patient-001`,
  `epic-note-001`, etc.). They are not real Epic IDs.
- Host names use `*.example.com` (reserved by RFC 2606).
- Coding systems used:
  - Public standards: LOINC (`http://loinc.org`), SNOMED CT, HL7 code systems.
  - Illustrative synthetic OID `urn:oid:1.2.840.114350.1.13.999.234` for
    Epic-local codes. The `.999.` arc is a deliberate sentinel so the
    `check_fixtures_synthetic.py` allowlist can distinguish it from any real
    Epic OID.
- Narrative text is invented. No PHI.

## Provenance

Each `<name>.json` has a sibling `<name>.provenance.json` describing what it
is derived from and which public references justify its shape. See
`PROVENANCE.md` for the cross-file summary.

## Trademark

"Epic" is a trademark of Epic Systems Corporation. The filename and directory
names are nominative references describing the integration target these
fixtures shape-match. See repo-root `NOTICE`.
