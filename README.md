# EPIC Suite

Local Epic-shaped FHIR / SMART-on-FHIR simulator plus a compat test harness for
the Chart Synthesis FHIR proxy path.

The suite has two halves:

- **`src/epic_sim`** — a FastAPI Epic FHIR R4 simulator. Implements SMART
  authorization-code flow, backend-services JWT flow, `.well-known/smart-configuration`,
  `metadata`, FHIR search / read / Binary endpoints, and pluggable Epic-style
  "quirks" (see `docs/EPIC_QUIRKS.md`) applied to fixture responses.
- **`src/fhir_proxy`** — the narrower production-side interface the Chart Synthesis
  product depends on: `FhirClient`, bundle executor, FHIR models, and PHI
  de-identification.

Tests replay Epic-shaped fixtures through both halves to verify behavior that
the product depends on, including:

- SMART well-known configuration and OAuth2 authorize + token endpoints
- Backend-services JWT client assertion flow
- Epic `DocumentReference` → `Binary` dereference
- Observation code filters with Epic-local codes plus LOINC codes
- HTML note stripping
- PHI display-name de-identification
- Binary access denial degrading into explicit bundle errors
- Unsupported FHIR search parameters becoming explicit bundle errors
- `_since`, `_include:iterate`, `_revinclude` rejection per configuration
- CareTeam inpatient filtering, VIP blocking, `meta.lastUpdated` stripping
- Fixture record/normalize pipeline for capturing sandbox responses

## Layout

```
src/
  epic_sim/       FastAPI simulator (auth, routes, quirks, fixtures)
  fhir_proxy/     Production-side FhirClient, executor, de-ID
tests/
  auth/           SMART well-known, auth-code, backend-services
  compat/         Epic adapter + proxy contract tests
  config/         Config loading
  http/           FHIR HTTP route coverage
  quirks/         Quirk engine (unit) + HTTP integration
  record/         Fixture normalization
configs/          default / permissive / strict_epic profiles
docs/EPIC_QUIRKS.md   Catalog of 44 Epic integration quirks (Q1–Q44)
scripts/record_sandbox.py   Capture sandbox responses into fixtures
```

## Run

From this folder:

```powershell
python -m pip install -e .
python -m pytest -q
```

For an isolated environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e .
.\.venv\Scripts\python -m pytest -q
```

Current suite: **79 tests** across `auth`, `compat`, `config`, `http`, `quirks`,
and `record`. Update this number when the suite grows.

## What Passing Tests Prove

Passing tests mean the simulator and the proxy/adapter code handle the
Epic-shaped behaviors captured in `tests/**/fixtures/` and the quirk rules in
`src/epic_sim/quirks/`.

Passing tests do not prove live Epic compatibility by themselves. Fixtures must
be calibrated against real Epic sandbox or customer test-environment responses.
When Epic changes behavior, capture a new fixture via `scripts/record_sandbox.py`,
update the relevant quirk or route, and keep the test local and repeatable.

See `docs/QUIRK_COVERAGE.md` for the quirk-to-test coverage matrix.
