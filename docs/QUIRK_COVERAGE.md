# Quirk Coverage Matrix

Maps each quirk in `EPIC_QUIRKS.md` (Q1–Q44) to the test(s) that cover it.

**Status legend**
- ✅ covered — at least one test asserts the simulator/proxy behavior
- 🟡 partial — behavior is implemented or adjacent behavior is tested, but the specific quirk is not fully pinned
- ❌ gap — no test; either not implemented or implemented without coverage
- ➖ out-of-scope — cannot be tested locally (sandbox-only, timing-dependent, or UI/infra)

Last refreshed: 2026-04-18. Suite size at refresh: 79 tests.

---

## 1. Auth / SMART

| # | Quirk | Status | Test(s) |
|---|---|---|---|
| Q1 | JWT-only backend services auth — no client_secret fallback | ✅ | `tests/auth/test_backend_services.py::test_rejects_client_secret_when_jwt_required`, `::test_happy_path_client_credentials_with_jwt_assertion` |
| Q2 | Authorization code becomes JWT (not opaque) | 🟡 | `tests/auth/test_authorization_code.py::test_full_authorize_to_token_to_fhir_call` exercises the flow; the JWT-vs-opaque code shape is not explicitly asserted |
| Q3 | `online_access` silently granted as `offline_access` | ❌ | none |
| Q4 | `fhirUser` claim in id_token (not smart.user) | ❌ | none |
| Q5 | SMART well-known omits introspection/revocation/registration | ✅ | `tests/auth/test_well_known.py::test_omits_all_three_endpoints_by_default`, `::test_permissive_config_includes_all_endpoints` |
| Q6 | 2FA on provider test accounts blocks EHR launch | ➖ | sandbox-only |
| Q7 | JWT `jti` unique per exp window; max 151 chars | ✅ | `tests/auth/test_backend_services.py::test_rejects_oversized_jti`, `::test_rejects_jti_replay`, `::test_rejects_exp_too_far_in_future` |
| Q8 | `iss`/`aud` must match token URL or allowlist | ✅ | `tests/auth/test_backend_services.py::test_rejects_iss_sub_mismatch`, `::test_aud_allowlist_rejects_wrong_audience` |

Adjacent auth tests: `test_fhir_call_without_bearer_rejected`, `test_bad_bearer_rejected`, `test_code_single_use`, `test_auth_optional_when_config_disables`, `test_jwks_endpoint_returns_public_key`, `test_rejects_unknown_client`.

## 2. Search Params

| # | Quirk | Status | Test(s) |
|---|---|---|---|
| Q9 | Post-filtered params may return < `_count` | ✅ | `tests/quirks/test_quirks.py::test_post_filter_discards_tail`, `::test_post_filter_disabled_keeps_all` |
| Q10 | Unsupported params → OperationOutcome | ✅ | `tests/compat/test_epic_proxy_contract.py::test_unsupported_epic_search_param_becomes_bundle_error`; reject-mode quirks below |
| Q11 | Patient identifier system OID-based / site-specific | ❌ | none |
| Q12 | Patient search requires full MRN with `urn:oid:` prefix | ❌ | none |
| Q13 | `_since` not supported in bulk export | ✅ | `tests/quirks/test_quirks.py::test_rejects_since_when_bulk_disabled`, `tests/quirks/test_http_integration.py::test_since_rejected_by_default`, `::test_since_allowed_when_bulk_since_supported` |
| Q14 | `_include:iterate` / `_revinclude` not supported | ✅ | `tests/quirks/test_quirks.py::test_rejects_include_iterate`, `::test_rejects_revinclude`, `::test_ignore_mode_does_not_raise` |

## 3. Resource Shape

| # | Quirk | Status | Test(s) |
|---|---|---|---|
| Q15 | `meta.lastUpdated` not populated | ✅ | `tests/quirks/test_quirks.py::test_strip_meta_last_updated`, `::test_keep_meta_when_enabled`; `tests/record/test_normalize.py::TestNormalizeBundle::test_strips_resource_meta_lastupdated`, `TestNormalizeBinary::test_strips_volatile_meta` |
| Q16 | FHIR IDs are opaque base64 strings | ❌ | none |
| Q17 | CareTeam excludes inpatient members | ✅ | `tests/quirks/test_quirks.py::test_filter_careteam_inpatient` |
| Q18 | Consent.Search returns metadata only | ❌ | none |
| Q19 | Condition bulk export access errors | ✅ | `tests/quirks/test_quirks.py::test_condition_access_errors_injected` |
| Q20 | Observation hidden if only in DiagnosticReport.result | ❌ | none |
| Q21 | Observation.hasMember nested members not returned | ✅ | `tests/quirks/test_quirks.py::test_strip_has_member_on_observation` |
| Q22 | MRN identifier `type.text "MRN"` not guaranteed | ✅ | `tests/quirks/test_quirks.py::test_mrn_type_text_applied` |

## 4. References & Dereferencing

| # | Quirk | Status | Test(s) |
|---|---|---|---|
| Q23 | Binary 403 surfaces as bundle OperationOutcome | ✅ | `tests/quirks/test_quirks.py::test_binary_403_deterministic_blocks_when_rate_100`, `::test_binary_403_rate_zero_never_blocks`, `::test_binary_403_deterministic_same_id_same_result`; `tests/http/test_fhir_routes.py::TestBinary::test_unknown_binary_returns_404` (adjacent) |
| Q24 | DocumentReference → Binary required; content not inline | ✅ | `tests/quirks/test_quirks.py::test_docref_inline_data_stripped`, `::test_docref_inline_data_kept`; `tests/quirks/test_http_integration.py::test_docref_data_stripped_by_default`, `::test_docref_binary_url_preserved`; `tests/compat/test_epic_adapter_contract.py` |
| Q25 | Next-page pagination URL opaque / session-scoped | 🟡 | `tests/record/test_normalize.py::TestNormalizeBundle::test_replaces_session_scoped_next_link` (fixture side only; live pagination not exercised) |

## 5. Errors & Status Codes

| # | Quirk | Status | Test(s) |
|---|---|---|---|
| Q26 | Policy-driven 403 for VIP / restricted patients | ✅ | `tests/quirks/test_quirks.py::test_vip_patient_blocked`, `::test_vip_patient_not_blocked_when_not_listed`; `tests/quirks/test_http_integration.py::test_vip_patient_blocks_request` |
| Q27 | CDS Hooks suggestions update scratchpad, not FHIR | ❌ | none |
| Q28 | Bulk export kickoff "requested too recently" | ❌ | none |

## 6. Rate Limits & Pagination

| # | Quirk | Status | Test(s) |
|---|---|---|---|
| Q29 | Bulk export 24h per-group window | ❌ | none |
| Q30 | Document query daily caps | 🟡 | `tests/quirks/test_quirks.py::test_cap_page_size_truncates`, `tests/quirks/test_http_integration.py::test_max_page_size_caps_bundle` (page-size cap only; daily cap not modeled) |
| Q31 | `_count` is advisory; post-filtering can shrink pages | ✅ | `tests/quirks/test_quirks.py::test_post_filter_discards_tail`, `::test_cap_page_size_truncates` |

## 7. Extensions

| # | Quirk | Status | Test(s) |
|---|---|---|---|
| Q32 | Epic-local Observation codes alongside LOINC | ✅ | `tests/quirks/test_quirks.py::test_epic_local_code_added_to_observation`, `::test_epic_local_code_idempotent`; compat observation code-filter tests |
| Q33 | Gender identity via Epic-proprietary extension (pre-R5) | ✅ | `tests/quirks/test_quirks.py::test_gender_identity_extension_added` |
| Q34 | Medication orders carry Epic-specific category codes | ✅ | `tests/quirks/test_quirks.py::test_medication_category_added` |

## 8. Bulk Data

| # | Quirk | Status | Test(s) |
|---|---|---|---|
| Q35 | Group ID must be obtained out-of-band | ❌ | none |
| Q36 | Bulk export IDs may exceed 64-char FHIR limit | ❌ | none |
| Q37 | Bulk Accept header controls OO format, not file format | ❌ | none |
| Q38 | `X-Progress` header during polling; 202 → 200 | ❌ | none |

## 9. Write-back

| # | Quirk | Status | Test(s) |
|---|---|---|---|
| Q39 | Observation.Create requires pre-mapped LOINC → flowsheet | ❌ | none |
| Q40 | Appointment scheduling via `$find`/`$book` ops | ❌ | none |
| Q41 | Encounter cannot be created via FHIR API | ❌ | none |

## 10. Versioning

| # | Quirk | Status | Test(s) |
|---|---|---|---|
| Q42 | DSTU2/STU3 endpoints still live; version varies | ➖ | customer-infra-specific |

## 11. Other

| # | Quirk | Status | Test(s) |
|---|---|---|---|
| Q43 | CDS Hooks sandbox supports patient-view only | ➖ | sandbox-only |
| Q44 | SMART config update delays | ➖ | sandbox timing |

---

## Summary

| Status | Count |
|---|---|
| ✅ covered | 18 |
| 🟡 partial | 3 |
| ❌ gap | 19 |
| ➖ out-of-scope | 4 |
| **Total** | **44** |

### Priority gap backlog

Ordered by likely product impact on the Chart Synthesis FHIR proxy:

1. **Q11 / Q12** — Patient identifier OID + full-MRN search. Any customer onboarding needs this; currently no test or fixture.
2. **Q16** — Opaque base64 FHIR IDs. Product code should never parse or reconstruct IDs; lock with a round-trip test.
3. **Q20** — Observation hidden if only referenced via `DiagnosticReport.result`. Silent data-loss risk for chart synthesis.
4. **Q35 / Q36 / Q38** — Bulk data quirks. If bulk ingestion is on the roadmap, these need fixtures before first customer.
5. **Q3 / Q4** — `online_access` / `fhirUser` claim behavior. SMART-launch correctness; cheap to simulate.
6. **Q25** — Live opaque pagination (beyond fixture normalize). Add an integration test that follows a `next` link.
7. **Q27** — CDS Hooks scratchpad semantics. Only if CDS Hooks is in scope.
8. **Q29 / Q30** — Rate-limit / window behavior (full modeling). Fixture-only suffices until live sandbox work.

Gaps Q39–Q41 (write-back) are deferred pending product decision on write support.
