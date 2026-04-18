# Epic FHIR / SMART-on-FHIR Integration Quirks Catalog

**Purpose:** Seed a local Epic simulator (FastAPI + FixtureFhirClient) with reproducible Epic-shaped behaviors so developers can iterate without touching real Epic sandboxes or customer TST environments.

**Compiled:** 2026-04-17  
**Source window:** Primarily 2023–2026. Epic releases quarterly (Feb/May/Aug/Nov); release train noted where sources specify.

---

## Table of Contents

1. [Auth / SMART](#1-auth--smart)
   - [Q1] JWT-only backend services auth — no client_secret fallback
   - [Q2] Authorization code becomes JWT (not opaque) — breaks older clients
   - [Q3] online_access silently granted as offline_access
   - [Q4] fhirUser claim in id_token, not standard smart.user
   - [Q5] SMART well-known config omits introspection/revocation/registration endpoints
   - [Q6] 2FA on provider test accounts blocks SMART EHR launch
   - [Q7] JWT jti must be unique per exp window; max 151 chars
   - [Q8] iss/aud in JWT backend assertion must match token URL exactly or be allowlisted
2. [Search Params](#2-search-params)
   - [Q9] Post-filtered params introduced May 2024 — pages may have fewer than _count entries
   - [Q10] Unsupported search params return OperationOutcome (not silently ignored)
   - [Q11] Patient identifier system is OID-based, site-specific, not portable
   - [Q12] Patient search requires full MRN with urn:oid: prefix
   - [Q13] _since not supported in bulk export
   - [Q14] _include:iterate and _revinclude not supported
3. [Resource Shape](#3-resource-shape)
   - [Q15] meta.lastUpdated not populated on any resource
   - [Q16] FHIR IDs are opaque base64 strings, non-portable across sites
   - [Q17] CareTeam excludes inpatient treatment team members
   - [Q18] Consent.Search returns only metadata, not the document; provider-facing only
   - [Q19] Condition bulk export returns access errors for unauthorized subtypes
   - [Q20] Observation hidden if referenced only via DiagnosticReport.result
   - [Q21] Observation.hasMember nested group members not returned in default search/export
   - [Q22] MRN identifier type.text "MRN" is not guaranteed across sites
4. [References and Dereferencing](#4-references--dereferencing)
   - [Q23] Binary 403 for restricted documents surfaces as bundle OperationOutcome entry
   - [Q24] DocumentReference → Binary dereference required; content not inline
   - [Q25] Next-page pagination URL is opaque and session-scoped — do not reconstruct
5. [Errors and Status Codes](#5-errors--status-codes)
   - [Q26] Policy-driven 403 for VIP / restricted patients looks like scope failure
   - [Q27] CDS Hooks suggestions update scratchpad, NOT the FHIR server resource
   - [Q28] Bulk export kickoff 429-equivalent: "requested this Group too recently"
6. [Rate Limits and Pagination](#6-rate-limits--pagination)
   - [Q29] Bulk export per-group request window defaults to 24 hours
   - [Q30] Document query daily caps exist in production but not in sandbox
   - [Q31] _count is advisory; post-filtering can return fewer results per page
7. [Extensions](#7-extensions)
   - [Q32] Epic-local Observation codes alongside (or instead of) LOINC
   - [Q33] Patient gender identity carried via Epic-proprietary extension pre-R5
   - [Q34] Medication orders carry Epic-specific category codes (community / outpatient)
8. [Bulk Data](#8-bulk-data)
   - [Q35] Group ID must be obtained out-of-band — no FHIR Group.create API
   - [Q36] Bulk export IDs may exceed 64-character FHIR limit (toggle required)
   - [Q37] Bulk export Accept header controls OperationOutcome format, not file format
   - [Q38] X-Progress header present during polling; 202 until complete, then 200
9. [Write-back](#9-write-back)
   - [Q39] Observation.Create requires pre-mapped LOINC to flowsheet row
   - [Q40] Appointment scheduling uses $find / $book custom ops, not standard FHIR create
   - [Q41] Encounter cannot be created via FHIR API
10. [Versioning](#10-versioning)
    - [Q42] DSTU2 / STU3 endpoints still live at production sites; version varies per customer
11. [Other](#11-other)
    - [Q43] CDS Hooks sandbox only supports patient-view hook
    - [Q44] SMART config update delays in sandbox (OAuth2 errors resolve after 1-2 days)

---

## 1. Auth / SMART

### Q1 — JWT-only backend services auth — no client_secret fallback

**Category:** Auth/SMART  
**Behavior:** Epic's backend services (M2M) flow requires a signed JWT client assertion (`client_assertion_type: urn:ietf:params:oauth:client-assertion-type:jwt-bearer`). There is no symmetric shared-secret fallback for backend apps. The SMART client-js library's `.authorize()` does not support overriding `grant_type` and `assertion` by default, requiring developers to implement the token exchange manually.  
**Evidence:** "Epic EHR requires signed JWT for authorization for Tesseract but `.authorize()` does not support overriding default `grant_type` and assertion." — GitHub issue smart-on-fhir/client-js#145. Also: "Epic now requires the backend OAuth flow in order for any app to be approved to their marketplace." — ibid.  
**URLs:**
- https://github.com/smart-on-fhir/client-js/issues/145  
- https://medium.com/@hanzla1702/epic-fhir-implementing-backend-services-with-smart-oauth-2-0-8bcd8af0c6b0  

**Simulator recipe:**
```python
# config flag
backend_services_jwt_required: bool = True
# On token request: if grant_type != "client_credentials" or
# client_assertion_type != "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
# return 400 {"error": "invalid_request"}
```
Return fixture `auth_invalid_request_no_jwt.json` when wrong grant_type is sent.

**Frequency / severity:** Many reports. Blocks integration for any backend/M2M app that relies on client_secret flows.

---

### Q2 — Authorization code becomes JWT (not opaque) — breaks older clients

**Category:** Auth/SMART  
**Behavior:** Epic's sandbox changed authorization codes from opaque strings to JWT-formatted tokens (prefixed `eyJ…`). Clients that assume the code is opaque and pass it directly to the token endpoint receive `{"error": "invalid_grant", "error_description": null}`.  
**Evidence:** "Epic's new authorization_code with a jwt instead of an opaque code won't let me retrieve an access_token" — GitHub smart-on-fhir/client-js#87.  
**URL:** https://github.com/smart-on-fhir/client-js/issues/87  
**Simulator recipe:**
```python
auth_code_format: Literal["opaque", "jwt"] = "jwt"
# When jwt: issue eyJ... base64url-encoded code; validate on token exchange
# Inject: return 400 invalid_grant when code is replayed or structurally wrong
```
Fixture `token_invalid_grant.json`: `{"error":"invalid_grant","error_description":null}`

**Frequency / severity:** Moderate reports (sandbox change event). Blocks token exchange.

---

### Q3 — online_access silently granted as offline_access

**Category:** Auth/SMART  
**Behavior:** When an app requests `online_access` scope, Epic grants `offline_access` instead. The granted scope returned in the token response does not visibly include `offline_access`, causing validation failures in OAuth libraries that check returned scopes against requested scopes.  
**Evidence:** "Epic returns `offline_access` to the user but it is not visibly returned in the scope received" — community.fhir.org thread on Epic's refresh token / offline_access support.  
**URL:** https://groups.google.com/g/smart-on-fhir/c/K7N0dXMZUJc  
**Simulator recipe:**
```python
online_access_returns_offline: bool = True
# When scope contains "online_access": replace with "offline_access" in token response
# but omit from scope field in response body
```

**Frequency / severity:** Moderate. Causes scope mismatch errors in strict OAuth libraries; causes confusion about refresh token lifetime.

---

### Q4 — fhirUser claim in id_token, not standard smart.user

**Category:** Auth/SMART  
**Behavior:** When `openid` and `fhirUser` scopes are requested on R4, the user identifier is placed in the JWT payload as `fhirUser` (an absolute FHIR resource URL), NOT in the standard `profile` claim or as `smart.user.id`. The SMART client-js `client.user.read()` convenience method fails; developers must manually base64-decode the id_token and extract `fhirUser`.  
**Evidence:** "the `id_token` returned after the oauth response will have `fhirUser` in its payload, which will be an absolute reference to the FHIR resource" — GitHub smart-on-fhir/client-js#105. Also: "Epic App Orchard Launcher adds STATIC items to their OIDC discovery metadata including `id_token_signing_alg_values_supported` (defaults to `RS256`) and `response_types_supported` (showing `code` rather than `id_token`)."  
**URL:** https://github.com/smart-on-fhir/client-js/issues/105  
**Simulator recipe:**
```python
fhir_user_in_id_token: bool = True
# id_token payload: include "fhirUser": "https://<base>/api/FHIR/R4/Practitioner/abc123"
# Do NOT include "profile" claim
```
Fixture `id_token_fhiruser_claim.json`.

**Frequency / severity:** Many reports. Breaks any app relying on standard OIDC `profile` claim or smart.user shorthand.

---

### Q5 — SMART well-known config omits introspection / revocation / registration endpoints

**Category:** Auth/SMART  
**Behavior:** Epic's `/.well-known/smart-configuration` endpoint does not include `introspection_endpoint`, `revocation_endpoint`, or `registration_endpoint`. The discovery document only exposes `authorization_endpoint`, `token_endpoint`, `jwks_uri`, `issuer`, and capability lists. Apps that require dynamic client registration or token introspection must hardcode or skip these features.  
**Evidence:** Direct fetch of `https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/.well-known/smart-configuration` confirms absence. Standard SMART App Launch v2 recommends these fields.  
**URL:** https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/.well-known/smart-configuration  
**Simulator recipe:**
```python
omit_introspection_endpoint: bool = True
omit_revocation_endpoint: bool = True
omit_registration_endpoint: bool = True
# Return fixture smart_configuration_epic.json (no introspection/revocation/registration fields)
```

**Frequency / severity:** Moderate. Annoyance for apps that auto-discover token introspection; blocks fully automated client registration.

---

### Q6 — 2FA on provider test accounts blocks SMART EHR launch

**Category:** Auth/SMART  
**Behavior:** When Epic automatically enrolls provider test accounts in two-factor authentication (2FA), the SMART EHR launch authorization flow fails or stalls at the MFA challenge screen. The fix is to disable 2FA for test accounts. This does not affect sandbox accounts but can occur in customer TST environments.  
**Evidence:** "Providers setting up 2FA automatically for new users caused authorization errors, which were resolved by disabling 2FA for test accounts." — community report in SMART on FHIR Google Group.  
**URL:** https://groups.google.com/g/smart-on-fhir/c/vtukyF_IO8s  
**Simulator recipe:**
```python
mfa_challenge_enabled: bool = False  # toggle to True to simulate 2FA block
# When enabled: redirect to fixture auth_mfa_required.html instead of completing auth flow
# Return 403 with OperationOutcome if app retries without completing MFA
```

**Frequency / severity:** Low in sandbox, moderate in TST. Blocks launch completely when hit.

---

### Q7 — JWT jti must be unique per exp window; max 151 characters

**Category:** Auth/SMART  
**Behavior:** The `jti` (JWT ID) claim in backend-services JWT assertions must be no longer than 151 characters AND must not be reused during the JWT's validity period (before `exp` time). The `exp` must be at most 5 minutes in the future at time of receipt. Violations return auth errors with no indication of which constraint failed.  
**Evidence:** "The jti must be no longer than 151 characters and cannot be reused during the JWT's validity period." — docs.intraconnects.com Epic JWT documentation, citing Epic spec.  
**URL:** https://docs.intraconnects.com/docs/ehr-basics/epic/Auth/jwt/  
**Simulator recipe:**
```python
jwt_jti_max_length: int = 151
jwt_exp_max_minutes: int = 5
jwt_jti_replay_check: bool = True
# Validate on token request; return 400 {"error":"invalid_client"} on violation
```
Fixture `auth_invalid_client_jti.json`.

**Frequency / severity:** Moderate. Common when copying JWTs across requests or using UUIDs truncated incorrectly.

---

### Q8 — iss/aud in JWT backend assertion must match token URL or be allowlisted

**Category:** Auth/SMART  
**Behavior:** Epic community members often route traffic through proxy servers, so the token URL the JWT is posted to differs from the URL the authorization server knows. Epic requires the `aud` claim to exactly match the token endpoint URL or be on an admin-configured allowlist. The `sub` and `iss` claims must also match the registered `client_id`. Developers behind proxies routinely get `invalid_client` errors.  
**Evidence:** "Epic community member systems will route web service traffic through a proxy server, in which case the URL the JWT is posted to is not known to the authorization server, and the JWT will be rejected. For such cases, Epic community member administrators can add additional audience URLs to the allowlist." — docs.intraconnects.com Backend Auth.  
**URL:** https://docs.intraconnects.com/docs/ehr-basics/epic/Auth/Backend/  
**Simulator recipe:**
```python
jwt_aud_allowlist: list[str] = []  # empty = only token endpoint URL accepted
# Validate aud claim; return {"error":"invalid_client"} if no match
```

**Frequency / severity:** Moderate in proxy-heavy enterprise environments. Blocks all backend auth.

---

## 2. Search Params

### Q9 — Post-filtered params introduced May 2024 — pages may have fewer than _count entries

**Category:** Search params  
**Behavior:** Starting in Epic's May 2024 release, certain search parameters use a "post-filtering" mechanism: Epic first retrieves `_count` results matching native params, then filters that set down by additional post-filter params. This means pages can return fewer entries than `_count` without a `next` link, looking like the last page when it is not. Naive clients that check `count(entries) < _count` to detect the last page will terminate pagination early.  
**Evidence:** "When responding to a request, the Epic FHIR server first retrieves all results that match your search using any native search parameters you've provided, then filters down those results based on the additional post-filtered parameters you've specified." — fhir.epic.com Specifications. "If many of those results are filtered out, the final result set will be smaller than `_count`." — search results summary.  
**URL:** https://fhir.epic.com/Specifications  
**Release train:** May 2024+  
**Simulator recipe:**
```python
post_filter_enabled: bool = True
post_filter_discard_rate: float = 0.3  # fraction of results silently dropped after _count fetch
# Return bundle with fewer entries than _count but still include "next" link
```
Fixture `search_post_filtered_short_page.json`.

**Frequency / severity:** Many reports since May 2024. Causes silent data truncation for any client terminating on `entries < _count`.

---

### Q10 — Unsupported search params return OperationOutcome, not silent ignore

**Category:** Search params  
**Behavior:** When a client sends a search parameter that Epic does not support (e.g., an unrecognized modifier), Epic returns an HTTP 400 with an `OperationOutcome` resource rather than silently ignoring the parameter and returning results. This is stricter than many other FHIR servers that silently drop unknown params. However, the error shape is Epic-specific — issue severity is `error`, code is `not-supported`.  
**Evidence:** "Invoking unsupported operations on Epic on FHIR services results in errors with appropriate OperationOutcome values returned that can be handled by the caller." — FHIRLink/Epic integration guide on Microsoft Tech Community.  
**URL:** https://techcommunity.microsoft.com/blog/healthcareandlifesciencesblog/fhirlink-connector-support-for-epic-on-fhir/4162824  
**Simulator recipe:**
```python
unsupported_param_behavior: Literal["reject", "ignore"] = "reject"
# When "reject": return 400 + fixture unsupported_search_param_outcome.json
```
Fixture `unsupported_search_param_outcome.json`:
```json
{"resourceType":"OperationOutcome","issue":[{"severity":"error","code":"not-supported","diagnostics":"Search parameter not supported."}]}
```

**Frequency / severity:** Many reports. Blocks integration when devs add parameters that work on other FHIR servers.

---

### Q11 — Patient identifier system is OID-based, site-specific, not portable

**Category:** Search params  
**Behavior:** To search a Patient by MRN, the identifier system must use Epic's OID arc (`urn:oid:1.2.840.114350.*`), and the exact OID suffix differs per Epic customer. The sandbox uses a fixed OID for testing, but production OIDs must be obtained from each site. Additionally, the `identifier.type.text` value "MRN" is not guaranteed across sites.  
**Evidence:** "In the Epic sandbox, you can use an ID system of `urn:oid:1.2.840.114350.1.13.0.1.7.5.737384.14` to search by MRN... Note: this system value will differ in each customer environment." — docs.redoxengine.com. "Do NOT rely on this saying 'MRN' at every customer!" — Redox docs.  
**URL:** https://docs.redoxengine.com/fhir-api-actions/patients/search-for-a-patient-with-identifier/  
**Simulator recipe:**
```python
mrn_oid_system: str = "urn:oid:1.2.840.114350.1.13.0.1.7.5.737384.14"
# Require exact system match in identifier search; return empty bundle on wrong OID
# Configurable per simulated "site"
```

**Frequency / severity:** Many reports. Common first-integration stumbling block.

---

### Q12 — Patient search with _id uses FHIR logical ID, not MRN

**Category:** Search params  
**Behavior:** Epic's Patient `_id` search parameter takes the Epic FHIR logical ID (opaque base64 string), not the MRN or any external identifier. Searching by MRN requires the `identifier` parameter with the correct OID system (see Q11). Confusing the two results in empty bundles with no error.  
**Evidence:** From tactionsoft.com 2026 integration guide: "Epic FHIR IDs are opaque, instance-specific identifiers that are base64-encoded, non-portable across environments, and must be resolved from external identifiers like NPI before they can anchor a reliable identity record."  
**URL:** https://www.tactionsoft.com/blog/epic-ehr-integration-guide/  
**Simulator recipe:**
```python
# Patient/_id lookup: match only against fixture FHIR IDs (opaque)
# Patient?identifier= : match against MRN + OID system
# Return empty bundle (not error) when _id looks like an MRN
```

**Frequency / severity:** Many reports. Silent failure (empty bundle) is hard to diagnose.

---

### Q13 — _since not supported in bulk export

**Category:** Search params  
**Behavior:** Epic's bulk export (`$export`) does not implement the `_since` parameter defined in the Bulk Data IG. Attempting to pass `_since` does not filter results to records updated after the given instant; the parameter is silently ignored or rejected. Use `_typeFilter` with date-range criteria as a workaround.  
**Evidence:** "Epic hasn't implemented the `_since` parameter for bulk exports yet, but it has implemented `_typeFilter`." — GitHub smart-on-fhir/cumulus discussion #5.  
**URL:** https://github.com/smart-on-fhir/cumulus/discussions/5  
**Simulator recipe:**
```python
bulk_since_supported: bool = False
# When _since present and bulk_since_supported=False: ignore parameter silently
# Log warning; return full export without date filtering
```

**Frequency / severity:** Many reports. Forces full re-exports for incremental sync use cases.

---

### Q14 — _include:iterate and _revinclude not supported

**Category:** Search params  
**Behavior:** Epic does not support `_include:iterate` (recursive include) or `_revinclude` for Observation resources. Attempts to retrieve nested `Observation.hasMember` groups or related resources via these params return an OperationOutcome or are silently ignored, leaving data incomplete.  
**Evidence:** "No support for `_include:iterate` for nested observation groups. No support for `_revinclude` to retrieve related Observations." — GitHub smart-on-fhir/cumulus discussion #5.  
**URL:** https://github.com/smart-on-fhir/cumulus/discussions/5  
**Simulator recipe:**
```python
include_iterate_supported: bool = False
revinclude_supported: bool = False
# Return 400 OperationOutcome or silently drop; configurable per toggle
```

**Frequency / severity:** Moderate. Impacts any app doing graph traversal via includes.

---

## 3. Resource Shape

### Q15 — meta.lastUpdated not populated on any resource

**Category:** Resource shape  
**Behavior:** Epic does not populate `meta.lastUpdated` on any FHIR resource. The field is absent or null. This breaks any incremental sync logic that relies on `meta.lastUpdated` to determine which records changed. Developers must process exports chronologically and use `_typeFilter` with explicit date ranges.  
**Evidence:** "Epic does not provide metadata about when each record was last updated (i.e. does not populate the `meta.lastUpdated` FHIR field)." — GitHub smart-on-fhir/cumulus discussion #5. Process exports chronologically to avoid overwriting newer data with older batches.  
**URL:** https://github.com/smart-on-fhir/cumulus/discussions/5  
**Simulator recipe:**
```python
populate_meta_last_updated: bool = False
# Strip meta.lastUpdated from all resource fixtures before serving
```

**Frequency / severity:** Many reports. Blocks incremental sync designs.

---

### Q16 — FHIR IDs are opaque base64 strings, non-portable across sites

**Category:** Resource shape  
**Behavior:** All Epic FHIR resource IDs are opaque, base64url-encoded strings that are instance-specific. The same patient has a different FHIR ID at every Epic customer site. IDs cannot be bookmarked or used cross-site. The id_token `fhirUser` claim contains an absolute URL including the base URL of the specific Epic instance.  
**Evidence:** "Epic FHIR IDs are opaque, instance-specific identifiers that are base64-encoded, non-portable across environments." — stitchflow.com Epic User Management API guide.  
**URL:** https://www.stitchflow.com/user-management/epic/api  
**Simulator recipe:**
```python
fhir_id_format: Literal["opaque_b64", "uuid"] = "opaque_b64"
# Generate IDs as base64url(sha256(internal_id + site_salt))
# Return different IDs for same logical patient across simulated sites
```

**Frequency / severity:** Many reports. Breaks any cross-site identity resolution that relies on FHIR IDs.

---

### Q17 — CareTeam excludes inpatient treatment team members

**Category:** Resource shape  
**Behavior:** Epic's `CareTeam` resource returns longitudinal care team assignments and providers with recent visits, but explicitly excludes inpatient treatment team members. Those members appear only as `Encounter.participant` entries in the relevant Encounter resource. Apps expecting a unified care team from `CareTeam` will miss inpatient providers.  
**Evidence:** "The patient's inpatient treatment team is not included in this resource. Inpatient treatment team members are instead included as participants in the relevant Encounter resource." — fhir.epic.com Specifications (Encounter.Read API 825).  
**URL:** https://fhir.epic.com/Specifications?api=825  
**Simulator recipe:**
```python
careteam_excludes_inpatient: bool = True
# CareTeam fixture omits inpatient_team_members[] array
# Encounter fixture includes same members under participant[]
```

**Frequency / severity:** Moderate. Causes care-gap analysis errors for apps covering inpatient workflows.

---

### Q18 — Consent.Search returns only metadata, not the document; provider-facing only

**Category:** Resource shape  
**Behavior:** Epic's `Consent` resource search returns only metadata (consent type, effective period) corresponding to consent documents stored as Epic Documents. The full document content is not returned. Additionally, this resource is restricted to provider-facing applications; patient-facing apps receive an error.  
**Evidence:** "The Consent.Search interaction returns only metadata about the patient consent document(s) on file, such as the type of consent and the effective period. This resource does not return the consent document itself." Also: "The Consent resource is intended only for provider-facing applications. Patient-facing applications cannot use this resource." — fhir.epic.com documentation.  
**URL:** https://fhir.epic.com/Documentation  
**Simulator recipe:**
```python
consent_returns_full_document: bool = False
consent_patient_facing_allowed: bool = False
# Consent resource fixture: include only type + period, no attachment
# When patient-context token used: return 403 OperationOutcome
```

**Frequency / severity:** Low reports. Impacts compliance apps expecting document content.

---

### Q19 — Condition bulk export returns access errors for unauthorized subtypes

**Category:** Resource shape  
**Behavior:** Epic's bulk export for `Condition` attempts to access all Condition subtypes (e.g., "Dental Finding") even for API types the client has no access to. Error entries appear in the export output for inaccessible subtypes. These errors are expected and safe to ignore, but clients that fail on any error entry will break.  
**Evidence:** "Epic's bulk export for Conditions will give errors even for API types you haven't been given access to — for example, Epic's export will attempt to access those records behind the scenes and give you errors, but this is fine and expected and can be ignored." — GitHub smart-on-fhir/cumulus discussion #5.  
**URL:** https://github.com/smart-on-fhir/cumulus/discussions/5  
**Simulator recipe:**
```python
condition_bulk_inject_access_errors: bool = True
condition_inaccessible_subtypes: list[str] = ["dental-finding", "encounter-diagnosis-restricted"]
# Include OperationOutcome error entries in Condition NDJSON file for inaccessible types
```
Fixture `condition_bulk_with_errors.ndjson`.

**Frequency / severity:** Moderate. Breaks clients that treat any export error as fatal.

---

### Q20 — Observation hidden if referenced only via DiagnosticReport.result

**Category:** Resource shape  
**Behavior:** If an Observation is referenced only via `DiagnosticReport.result` and is not independently searchable (e.g., not associated with a patient-level search index), Epic hides it from standalone Observation search results. The Observation exists but is only retrievable via the DiagnosticReport read + result dereference.  
**Evidence:** "Epic hides Observations referenced by `DiagnosticReport.result`" — GitHub smart-on-fhir/cumulus discussion #5.  
**URL:** https://github.com/smart-on-fhir/cumulus/discussions/5  
**Simulator recipe:**
```python
observation_hidden_in_dr_result: bool = True
# DR-result-only Observations: not included in Observation?patient= search
# Accessible via GET /Observation/{id} directly when ID known
# Accessible via DR.result[].reference dereference
```

**Frequency / severity:** Moderate. Causes incomplete lab result extraction when aggregating from Observation search alone.

---

### Q21 — Observation.hasMember nested group members not returned in default search

**Category:** Resource shape  
**Behavior:** Observations that are panel members (referenced via `Observation.hasMember`) are not returned in standard Observation search results. They must be fetched individually by ID or via a workaround crawl (SMART Fetch). This means a vital-signs panel search returns only the grouping Observation, not the systolic/diastolic component Observations.  
**Evidence:** "Epic hides nested `Observation.hasMember` group members. Workaround: manually query missing resources or use SMART Fetch." — GitHub smart-on-fhir/cumulus discussion #5.  
**URL:** https://github.com/smart-on-fhir/cumulus/discussions/5  
**Simulator recipe:**
```python
observation_include_has_member: bool = False
# Observation search returns only root panel Observations
# hasMember references present in resource body but not included in bundle
```

**Frequency / severity:** Moderate. Causes incomplete vital sign extraction; systolic/diastolic missed.

---

### Q22 — MRN identifier type.text "MRN" not guaranteed across sites

**Category:** Resource shape  
**Behavior:** Epic returns MRN identifiers with `identifier.type.text = "MRN"` in the sandbox. In production customer environments the text value can differ or be absent. Code that matches on `type.text == "MRN"` for identifier selection is fragile; the correct approach is to match on the site-specific `system` OID.  
**Evidence:** "Do NOT rely on this saying 'MRN' at every customer!" — Redox documentation on Patient identifier search.  
**URL:** https://docs.redoxengine.com/fhir-api-actions/patients/search-for-a-patient-with-identifier/  
**Simulator recipe:**
```python
mrn_type_text_value: str | None = "MRN"  # set to None or "Medical Record Number" to simulate site variation
```

**Frequency / severity:** Low. Subtle production-only failure after successful sandbox testing.

---

## 4. References & Dereferencing

### Q23 — Binary 403 for restricted documents surfaces as bundle OperationOutcome entry

**Category:** References & dereferencing  
**Behavior:** When a patient has a restricted (e.g., confidential mental health) document, the Binary resource referenced from a DocumentReference returns HTTP 403. Epic surfaces this as an `OperationOutcome` error entry inside the Bundle response rather than failing the entire search request. Clients that only inspect `entry.resource` and skip entries without a `resource` will silently miss these denial signals.  
**Evidence:** Already implemented in the simulator. Documented as the existing `Binary 403 denials surfaced as bundle errors` behavior described in the simulator context.  
**URL:** https://fhir.epic.com/Documentation  
**Simulator recipe:**
```python
binary_403_rate: float = 0.0  # fraction of Binary requests that return 403
# Inject OperationOutcome entry in containing Bundle; HTTP status 200 on bundle
```
Fixture `binary_403_bundle_entry.json`.

**Frequency / severity:** Many reports. Blocks note retrieval for restricted patient charts.

---

### Q24 — DocumentReference content is always via Binary reference, never inline

**Category:** References & dereferencing  
**Behavior:** Epic's DocumentReference never includes inline `content.attachment.data` (base64). Content is always a URL reference to a Binary resource (`content.attachment.url`). Clients must follow the Binary reference to retrieve note content, incurring an additional HTTP round trip per document. The Binary resource returns `contentType: text/html` for clinical notes (HTML rendered notes) or `application/pdf` for scanned documents.  
**Evidence:** From simulator context: "DocumentReference→Binary→base64 dereference" is a documented pattern. Epic's DocumentReference spec at open.epic.com confirms URL-based attachment referencing.  
**URL:** https://open.epic.com/Clinical/Document  
**Simulator recipe:**
```python
docref_inline_data: bool = False
# Always return content.attachment.url pointing to /Binary/{id}
# Binary resource: contentType configurable ("text/html" or "application/pdf")
```

**Frequency / severity:** Many reports. Requires two-step fetch; breaks one-shot document extraction.

---

### Q25 — Next-page pagination URL is opaque and session-scoped — do not reconstruct

**Category:** References & dereferencing  
**Behavior:** The `link[relation=next]` URL in a search Bundle is an opaque, session-scoped cursor. It must be used verbatim; reconstructing it from query parameters fails. Modifying query parameters mid-session (e.g., adding a filter while on page 2) causes an error. Some implementations expire the cursor on session end.  
**Evidence:** "When paging, respect any session or cursor tokens returned by Epic; some implementations treat the query and its pages as a single session context. If you modify query parameters mid-page, you may receive an error." — 6b.health Epic FHIR integration guide.  
**URL:** https://6b.health/insight/exploring-epics-available-fhir-resources-from-appointment-to-allergy-data/  
**Simulator recipe:**
```python
pagination_cursor_opaque: bool = True
pagination_cursor_ttl_seconds: int = 300  # cursor expires after 5 minutes
# On next-link follow: validate cursor token, return 410 Gone or 400 on expired/invalid
```
Fixture `pagination_cursor_expired.json`.

**Frequency / severity:** Moderate. Causes silent pagination failure when clients reconstruct URLs.

---

## 5. Errors & Status Codes

### Q26 — Policy-driven 403 for VIP / restricted patients looks like scope failure

**Category:** Errors & status codes  
**Behavior:** When a provider accesses a VIP or confidential patient (Break-the-Glass scenario), Epic returns HTTP 403 with an OperationOutcome that includes a message about restricted access. This looks identical to a missing-scope 403. The guidance is to show users a neutral message, not to expose the "restricted" language to the patient. Backend clients that conflate this with authorization failures loop on re-auth.  
**Evidence:** "If your call fails with a message indicating restricted access, don't pass that phrasing through to the patient; show a neutral message." — 6b.health Epic FHIR integration guide. Break-the-Glass is Epic's VIP protection requiring password re-entry and HIPAA officer notification.  
**URL:** https://6b.health/insight/exploring-epics-available-fhir-resources-from-appointment-to-allergy-data/  
**Simulator recipe:**
```python
vip_patient_ids: list[str] = ["Patient/vip-test-001"]
btg_403_rate: float = 0.0  # set >0 to randomly inject VIP denial
# Return 403 + fixture vip_restricted_outcome.json for configured patient IDs
```
Fixture `vip_restricted_outcome.json`:
```json
{"resourceType":"OperationOutcome","issue":[{"severity":"error","code":"forbidden","diagnostics":"Access to this patient record is restricted."}]}
```

**Frequency / severity:** Low in sandbox, real in production. Can cause re-auth loops.

---

### Q27 — CDS Hooks suggestions update scratchpad, NOT FHIR server

**Category:** Errors & status codes  
**Behavior:** When a CDS Hooks service returns `suggestions` with `actions`, those actions modify the EHR's in-memory draft scratchpad (e.g., the draft prescription on screen), not the FHIR server. Attempting to use the `actions` property to write to the FHIR server has no effect or results in an error. This is a common misunderstanding.  
**Evidence:** "Suggestions that are accepted change the state of the 'scratchpad' or the draft resources on the practitioner's screen... It doesn't immediately change the state of the MedicationOrder resource on the FHIR Server. CDS Suggestions do not act on the FHIR Server directly. Do not try to modify resources on the FHIR Server using the actions property of suggestions." — Epic CDS Hooks documentation.  
**URL:** https://fhir.epic.com/Documentation?docId=cds-hooks  
**Simulator recipe:**
```python
cds_hooks_actions_hit_fhir: bool = False
# CDS Hooks suggestion actions: return 200 accepted but do NOT modify FHIR resources
# Log action to scratchpad_actions[] list only
```

**Frequency / severity:** Moderate. Causes write-back logic to silently fail.

---

### Q28 — Bulk export kickoff 429-equivalent: "requested this Group too recently"

**Category:** Errors & status codes  
**Behavior:** If a client kicks off a bulk export for the same Group before the configured request window (default 24 hours) has elapsed, Epic returns an HTTP 429-like error: "Request not allowed: The Client requested this Group too recently." The response does not include a standard `Retry-After` header. Changing the window requires Epic admin configuration (`FHIR_BULK_CLIENT_REQUEST_WINDOW_TBL`).  
**Evidence:** "Error processing Bulk Data Kickoff request: Request not allowed: The Client requested this Group too recently" — GitHub smart-on-fhir/cumulus discussion #5. "Default 24-hour window between bulk exports; requires `FHIR_BULK_CLIENT_REQUEST_WINDOW_TBL` adjustment."  
**URL:** https://github.com/smart-on-fhir/cumulus/discussions/5  
**Simulator recipe:**
```python
bulk_request_window_hours: int = 24
# Track last kickoff time per group_id; return 429 + fixture bulk_too_recent.json
```
Fixture `bulk_too_recent.json`:
```json
{"resourceType":"OperationOutcome","issue":[{"severity":"error","code":"throttled","diagnostics":"Request not allowed: The Client requested this Group too recently."}]}
```

**Frequency / severity:** Many reports. Blocks daily incremental exports.

---

## 6. Rate Limits & Pagination

### Q29 — Bulk export per-group request window defaults to 24 hours

**Category:** Rate limits & pagination  
**Behavior:** Epic enforces a per-client, per-group cooldown on bulk export kickoff requests. The default window is 24 hours (configurable by the Epic admin). This is separate from general API rate limiting and is not documented with standard HTTP rate-limit headers. See also Q28.  
**Evidence:** See Q28 evidence above.  
**Simulator recipe:**
```python
bulk_group_cooldown_hours: int = 24  # per group_id per client_id
```

**Frequency / severity:** Many reports. Critical for automated nightly pipeline design.

---

### Q30 — Document query daily caps exist in production but not sandbox

**Category:** Rate limits & pagination  
**Behavior:** Some Epic API families (particularly document queries) impose undocumented daily request caps in production that do not exist in the public sandbox. These caps protect system performance. Developers discover them only after go-live when document retrieval fails mid-day with 429s or OperationOutcomes.  
**Evidence:** "Some API families may also apply daily caps — for example, on document queries — to protect system performance for all users." — 6b.health Epic FHIR integration guide.  
**URL:** https://6b.health/insight/exploring-epics-available-fhir-resources-from-appointment-to-allergy-data/  
**Simulator recipe:**
```python
docref_daily_cap: int | None = None  # set to integer to simulate production cap
docref_daily_count: int = 0  # reset at midnight UTC
# When cap exceeded: return 429 + fixture docref_daily_cap_outcome.json
```

**Frequency / severity:** Low reports (production-only, post-go-live surprise). Potentially high severity.

---

### Q31 — _count is advisory; post-filtering can return fewer results per page

**Category:** Rate limits & pagination  
**Behavior:** See Q9 for detailed behavior. Even when `_count` is specified, post-filtered search parameters (May 2024+) can cause pages to have fewer entries. Additionally, Epic may enforce internal caps on maximum page size that override large `_count` values. The `_count` parameter is advisory, not guaranteed.  
**Evidence:** From May 2024 Epic search parameter documentation and 6b.health: "Avoid unbounded searches; server-side paging is common and, in complex charts, inevitable."  
**URL:** https://fhir.epic.com/Specifications  
**Simulator recipe:**
```python
max_page_size: int = 100  # Epic internally caps at ~100 for most resources
# When _count > max_page_size: return max_page_size entries + next link
```

**Frequency / severity:** Moderate. Causes surprise for clients that expect exact page sizes.

---

## 7. Extensions

### Q32 — Epic-local Observation codes alongside (or instead of) LOINC

**Category:** Extensions  
**Behavior:** Epic Observation resources include Epic-internal coding system codes (e.g., `urn:oid:1.2.840.114350.1.13.5.1.7.2.707679`) alongside or instead of standard LOINC codes. Apps that only look at LOINC codings miss data. Some flowsheet rows have no LOINC mapping at all and return only the Epic-local code.  
**Evidence:** Already implemented in simulator as "Epic-local Observation codes alongside LOINC." From orbdoc.com Epic integration guide: "some flowsheet rows have LOINC codes mapped to them by default, which can be used in interface messages to indicate which flowsheet rows to file to."  
**URL:** https://orbdoc.com/learn/epic-integration-technical-guide/  
**Simulator recipe:**
```python
observation_include_epic_local_code: bool = True
epic_local_code_system: str = "urn:oid:1.2.840.114350.1.13.5.1.7.2.707679"
# Add coding entry with epic_local_code_system alongside LOINC
# Some fixtures: LOINC absent, only epic_local_code present
```

**Frequency / severity:** Many reports. Breaks any terminology-matching that assumes LOINC always present.

---

### Q33 — Patient gender identity carried via Epic-proprietary extension pre-R5

**Category:** Extensions  
**Behavior:** Epic stores gender identity and legal sex using proprietary FHIR extensions on the Patient resource in R4. These differ from the standard HL7 Gender Harmony extensions (`individual-genderIdentity`, etc.) introduced for R5. Apps consuming Patient.gender get only administrative sex; gender identity requires parsing Epic-specific extension URLs.  
**Evidence:** "Epic is working to integrate patients' gender identity information into EHRs" using proprietary extensions in R4. HL7 Gender Harmony extensions are the R5 standard. Becker's Hospital Review coverage of Epic gender identity work confirms Epic-specific approach.  
**URL:** https://www.beckershospitalreview.com/healthcare-information-technology/how-epic-is-adding-patient-gender-identity-to-ehrs-6-things-to-know/  
**Simulator recipe:**
```python
patient_gender_identity_extension: bool = True
gender_identity_extension_url: str = "http://open.epic.com/FHIR/StructureDefinition/patient-gender-identity"
# Add extension to Patient fixture with valueCodeableConcept
```

**Frequency / severity:** Low in most integrations. High severity for apps with gender-sensitive clinical logic.

---

### Q34 — MedicationRequest uses Epic-specific category codes

**Category:** Extensions  
**Behavior:** Epic's MedicationRequest resources include category codes from Epic-specific systems (e.g., `community`, `outpatient`) in addition to or instead of standard FHIR medication-request-category codes. Apps filtering by standard category codes like `inpatient` may miss medications if Epic uses a different value.  
**Evidence:** "The MedicationRequest resource covers all types of orders for medications for a patient, including inpatient medication orders as well as community orders." — FHIR spec context. Epic FHIR Medications API shows category as searchable parameter with Epic-specific values.  
**URL:** https://www.mulesoft.com/exchange/org.mule.examples/epic-fhir-r4-medications-api/minor/1.0/pages/Use%20case/  
**Simulator recipe:**
```python
medication_request_category_system: str = "http://terminology.hl7.org/CodeSystem/medicationrequest-category"
medication_request_epic_category: str = "community"  # or "outpatient"
# Return MedicationRequest with both standard and epic-specific category coding
```

**Frequency / severity:** Moderate. Causes medication list filtering failures.

---

## 8. Bulk Data

### Q35 — Group ID must be obtained out-of-band — no FHIR Group.create API

**Category:** Bulk data  
**Behavior:** Epic does not support creating `Group` resources via the FHIR API. Groups used for bulk export are defined by Epic administrators within the EHR (criteria-based, e.g., "all patients with condition X discharged in the last week"). The Group ID is communicated to the developer out-of-band (e.g., by email). `Group.read` permission is also not required to perform a bulk export on a group.  
**Evidence:** "the healthcare organization's admin (not Epic staff) will define the group, and send you the group ID via (for example) email." — FHIR Chat, Epic Bulk Data Export questions thread. "Epic does not require Group.read permissions to perform bulk exports."  
**URL:** https://chat-archive.fhir.org/stream/179166-implementers/topic/Epic.20Bulk.20Data.20Export.20questions.3F.html  
**Simulator recipe:**
```python
bulk_group_ids: list[str] = ["group-test-001", "group-test-002"]
# Only configured group_ids accepted for $export kickoff
# Return 404 for unknown group IDs
# No POST /Group endpoint
```

**Frequency / severity:** Many reports. Architectural constraint requiring out-of-band coordination.

---

### Q36 — Bulk export IDs may exceed 64-character FHIR limit

**Category:** Bulk data  
**Behavior:** In rare cases, Epic's bulk FHIR export generates resource IDs longer than the FHIR-mandated 64-character maximum. This violates the spec and causes parse failures in strict FHIR clients. The fix requires contacting Epic to enable a toggle that caps IDs at 64 characters when registering the API client.  
**Evidence:** "In rare cases, Epic's bulk FHIR export can generate IDs that are longer than the mandated 64-character limit, which may cause issues if you use another bulk export client. You have to reach out to Epic to cap it at 64 characters (there is a toggle for this when you register your API client)." — GitHub smart-on-fhir/cumulus discussion #5.  
**URL:** https://github.com/smart-on-fhir/cumulus/discussions/5  
**Simulator recipe:**
```python
bulk_oversized_id_rate: float = 0.0  # fraction of resources with oversized IDs
bulk_oversized_id_length: int = 80   # length when injected
# When rate > 0: randomly inject IDs of bulk_oversized_id_length in NDJSON output
```

**Frequency / severity:** Low (rare in production). High severity for strict clients — parse failure.

---

### Q37 — Bulk export Accept header controls OperationOutcome format, not file format

**Category:** Bulk data  
**Behavior:** The `Accept: application/fhir+json` header on the `$export` kickoff request controls the format of the synchronous `OperationOutcome` response body, NOT the format of the downloaded NDJSON files. The files are always NDJSON regardless of Accept header. Sending `Accept: application/ndjson` causes an error. Many developers misread this.  
**Evidence:** "The Bulk FHIR spec requires `application/fhir+json` on the export request, not ndjson. That accept header controls the OperationOutcome response format to `$export`, not the file format, which is ndjson." — Cooper Thompson, FHIR Chat, Epic Bulk Data Export questions thread.  
**URL:** https://chat-archive.fhir.org/stream/179166-implementers/topic/Epic.20Bulk.20Data.20Export.20questions.3F.html  
**Simulator recipe:**
```python
# Kickoff: validate Accept header is "application/fhir+json"
# Return 400 if Accept is "application/ndjson" or absent
# Files: always serve as application/ndjson MIME regardless
```

**Frequency / severity:** Moderate. Common first-encounter mistake.

---

### Q38 — Bulk export polling returns 202 with X-Progress until complete, then 200

**Category:** Bulk data  
**Behavior:** During bulk export polling, Epic returns HTTP 202 with `X-Progress` header (free-text, e.g., "50 ids processed") and `Retry-After` header indicating seconds to wait. When complete, the status URL returns HTTP 200 with the manifest JSON. There is no interim "failed" status code — errors appear in the manifest. Polling too frequently (ignoring Retry-After) may return errors.  
**Evidence:** "An X-Progress header will tell you how many ids have been processed." — search results. "When complete, a GET request to the polling location URL will return an HTTP status of 200." — FHIR Bulk Data spec and interopiO Epic R4 Gateway guide.  
**URL:** https://support.interopio.com/hc/en-us/articles/4419488428052-Bulk-Data-Export-in-the-Epic-R4-Gateway  
**Simulator recipe:**
```python
bulk_polling_duration_seconds: int = 30  # simulated export time
bulk_x_progress_template: str = "{n} ids processed"
# Return 202 with X-Progress + Retry-After until duration elapsed
# Then return 200 with manifest fixture
```

**Frequency / severity:** Low. Straightforward once behavior is known; X-Progress format is non-standard.

---

## 9. Write-back

### Q39 — Observation.Create requires pre-mapped LOINC to flowsheet row

**Category:** Write-back  
**Behavior:** Writing a new Observation to Epic requires that the `code.coding.code` (LOINC code) be pre-mapped to an Epic flowsheet row by an Epic admin. If the LOINC code is not mapped, the write fails with an Epic-specific error. The error message indicates a missing flowsheet mapping, not a generic validation error. Write access is per-customer and requires additional Epic configuration.  
**Evidence:** "creating internal Epic encounters via API may also be restricted... Epic surfaces distinct failures for missing flowsheet mappings or invalid LOINC codes." — orbdoc.com Epic integration guide.  
**URL:** https://orbdoc.com/learn/epic-integration-technical-guide/  
**Simulator recipe:**
```python
observation_write_mapped_loincs: list[str] = ["8302-2", "8867-4", "59408-5"]  # height, HR, SpO2
# POST /Observation: if code.coding not in mapped_loincs → return 422 + fixture
```
Fixture `observation_unmapped_loinc.json`:
```json
{"resourceType":"OperationOutcome","issue":[{"severity":"error","code":"invalid","diagnostics":"The LOINC code provided does not map to a configured flowsheet row."}]}
```

**Frequency / severity:** Many reports. Blocks vitals and device integration write-back.

---

### Q40 — Appointment scheduling uses $find / $book custom ops, not standard FHIR create

**Category:** Write-back  
**Behavior:** Epic does not support `POST /Appointment` (FHIR create) for scheduling. Instead, scheduling uses two custom operations: `Appointment.$find` (returns available slots matching criteria) and `Appointment.$book` (books a specific slot). These wrap the slot-finding and booking into Epic-specific workflows. Standard FHIR scheduling clients that use `POST /Appointment` will receive a 405 or 400.  
**Evidence:** "The standout scheduling feature in Epic's implementation is a pair of custom operations: `Appointment.$find` and `Appointment.$book`." — 6b.health Appointment resource guide. These are the only supported scheduling write operations.  
**URL:** https://6b.health/insight/exploring-epics-available-fhir-resources-from-appointment-to-allergy-data/  
**Simulator recipe:**
```python
appointment_create_supported: bool = False
appointment_find_op_supported: bool = True
appointment_book_op_supported: bool = True
# POST /Appointment → 405 Method Not Allowed
# POST /Appointment/$find → return fixture available_slots.json
# POST /Appointment/$book → return booked fixture or 409 conflict
```

**Frequency / severity:** Many reports. Standard FHIR scheduling clients are incompatible.

---

### Q41 — Encounter cannot be created via FHIR API

**Category:** Write-back  
**Behavior:** Epic's Encounter resource supports read and search but not create (`POST /Encounter`). Attempts to create an Encounter return 405 or 400. Encounter creation goes through Epic-internal workflows, not the FHIR layer.  
**Evidence:** "The Encounter resource typically supports read and search operations, but not creation via the FHIR API." — 6b.health Epic FHIR API integration guide.  
**URL:** https://6b.health/insight/epic-fhir-api-integration/  
**Simulator recipe:**
```python
encounter_create_supported: bool = False
# POST /Encounter → 405 + fixture encounter_create_not_supported.json
```

**Frequency / severity:** Moderate. Blocks clinical documentation apps that need to create encounters.

---

## 10. Versioning

### Q42 — DSTU2 / STU3 endpoints still live at production sites; version varies per customer

**Category:** Versioning  
**Behavior:** Different Epic customer sites may be running DSTU2, STU3, or R4 FHIR endpoints, depending on their Epic release train and configuration. The DSTU2 endpoint format is deprecated but retained for backward compatibility. Apps must discover or negotiate the FHIR version from the `CapabilityStatement` (or `Conformance` for DSTU2) before making resource requests. The same resource exists on all three endpoints but with different field names and structures.  
**Evidence:** "Epic supports DSTU2, STU3, and R4... The DSTU2 endpoint format... is deprecated but retained for backwards compatibility to support apps that already use this format." — emrdirect.com FHIR Version Support knowledge base.  
**URL:** https://www.emrdirect.com/kb/client-applications/fhir-version-support  
**Simulator recipe:**
```python
fhir_versions_active: list[str] = ["R4"]  # can add "STU3", "DSTU2"
# Route /api/FHIR/DSTU2/ → DSTU2-shaped fixtures
# Route /api/FHIR/STU3/ → STU3-shaped fixtures
# Route /api/FHIR/R4/ → R4-shaped fixtures (default)
```

**Frequency / severity:** Moderate. Version mismatches cause resource parse failures.

---

## 11. Other

### Q43 — CDS Hooks sandbox only supports patient-view hook

**Category:** Other  
**Behavior:** Epic's CDS Hooks simulator (the sandbox available at fhir.epic.com) only supports the `patient-view` hook for testing. Testing other hooks (`order-select`, `order-sign`) requires using App Orchard Test System (TS) or a real Epic instance. Epic's production implementation supports `patient-view`, `order-select`, and `order-sign` natively as a CDS client (not server).  
**Evidence:** "The CDS Hooks simulator currently only supports the patient-view hook. You'd need to test with your App Orchard TS for other hooks." — FHIR Chat, Epic CDS Hook Simulator thread. "We are an EHR, and so we have a CDS Client implementation. We do not have a CDS Server implementation."  
**URL:** https://chat-archive.fhir.org/stream/179159-cds-hooks/topic/Epic.20CDS.20Hook.20Simulator.3F.html  
**Simulator recipe:**
```python
cds_hooks_supported_hooks: list[str] = ["patient-view"]  # expand for full sim
# Return 400 for unsupported hook types
# Act as CDS client only: expose /cds-services discovery endpoint
```

**Frequency / severity:** Moderate. Forces App Orchard TS dependency for hook testing.

---

### Q44 — SMART config update delays in sandbox (OAuth2 errors resolve after 1-2 days)

**Category:** Other  
**Behavior:** In Epic's public sandbox (fhir.epic.com), configuration changes (app registration updates, scope changes, key uploads) can take hours or up to 1-2 days to propagate. OAuth2 errors (`invalid_client`, `invalid_scope`) that appear immediately after a configuration change often self-resolve without any code change. This is specific to the shared sandbox, not production environments.  
**Evidence:** "The Epic sandbox is known for configuration update delays, with OAuth2 errors sometimes being resolved by waiting a day or two." — SMART on FHIR Google Group discussion, Getting OAuth2 Error Epic EHR launch thread.  
**URL:** https://groups.google.com/g/smart-on-fhir/c/vtukyF_IO8s  
**Simulator recipe:**
```python
config_propagation_delay_seconds: int = 0  # set to simulate delay
# When delay > 0: return stale config for config_propagation_delay_seconds after registration
# Return 401 invalid_client during delay window
```

**Frequency / severity:** Many reports (sandbox-specific). Annoying but not production-blocking.

---

## Simulator Config Surface

The following is a proposed `SimulatorConfig` Pydantic schema rolling up all injectable quirk flags from the catalog above.

```python
from pydantic import BaseModel, Field
from typing import Literal

class SimulatorConfig(BaseModel):
    # === Auth / SMART ===
    backend_services_jwt_required: bool = True
    auth_code_format: Literal["opaque", "jwt"] = "jwt"
    online_access_returns_offline: bool = True
    fhir_user_in_id_token: bool = True
    omit_introspection_endpoint: bool = True
    omit_revocation_endpoint: bool = True
    omit_registration_endpoint: bool = True
    mfa_challenge_enabled: bool = False
    jwt_jti_max_length: int = 151
    jwt_exp_max_minutes: int = 5
    jwt_jti_replay_check: bool = True
    jwt_aud_allowlist: list[str] = Field(default_factory=list)
    config_propagation_delay_seconds: int = 0

    # === Search Params ===
    post_filter_enabled: bool = True
    post_filter_discard_rate: float = 0.3
    unsupported_param_behavior: Literal["reject", "ignore"] = "reject"
    mrn_oid_system: str = "urn:oid:1.2.840.114350.1.13.0.1.7.5.737384.14"
    bulk_since_supported: bool = False
    include_iterate_supported: bool = False
    revinclude_supported: bool = False
    max_page_size: int = 100

    # === Resource Shape ===
    populate_meta_last_updated: bool = False
    fhir_id_format: Literal["opaque_b64", "uuid"] = "opaque_b64"
    careteam_excludes_inpatient: bool = True
    consent_returns_full_document: bool = False
    consent_patient_facing_allowed: bool = False
    condition_bulk_inject_access_errors: bool = True
    condition_inaccessible_subtypes: list[str] = Field(
        default=["dental-finding", "encounter-diagnosis-restricted"]
    )
    observation_hidden_in_dr_result: bool = True
    observation_include_has_member: bool = False
    mrn_type_text_value: str | None = "MRN"

    # === References & Dereferencing ===
    binary_403_rate: float = 0.0
    docref_inline_data: bool = False
    pagination_cursor_opaque: bool = True
    pagination_cursor_ttl_seconds: int = 300

    # === Errors & Status Codes ===
    vip_patient_ids: list[str] = Field(default_factory=list)
    btg_403_rate: float = 0.0
    cds_hooks_actions_hit_fhir: bool = False

    # === Rate Limits & Pagination ===
    bulk_request_window_hours: int = 24
    docref_daily_cap: int | None = None
    bulk_group_cooldown_hours: int = 24

    # === Extensions ===
    observation_include_epic_local_code: bool = True
    epic_local_code_system: str = "urn:oid:1.2.840.114350.1.13.5.1.7.2.707679"
    patient_gender_identity_extension: bool = True
    gender_identity_extension_url: str = (
        "http://open.epic.com/FHIR/StructureDefinition/patient-gender-identity"
    )
    medication_request_epic_category: str = "community"

    # === Bulk Data ===
    bulk_group_ids: list[str] = Field(default=["group-test-001"])
    bulk_oversized_id_rate: float = 0.0
    bulk_oversized_id_length: int = 80
    bulk_polling_duration_seconds: int = 30
    bulk_x_progress_template: str = "{n} ids processed"

    # === Write-back ===
    observation_write_mapped_loincs: list[str] = Field(
        default=["8302-2", "8867-4", "59408-5", "29463-7", "8310-5"]
    )
    appointment_create_supported: bool = False
    appointment_find_op_supported: bool = True
    appointment_book_op_supported: bool = True
    encounter_create_supported: bool = False

    # === Versioning ===
    fhir_versions_active: list[str] = Field(default=["R4"])

    # === CDS Hooks ===
    cds_hooks_supported_hooks: list[str] = Field(default=["patient-view"])
```

---

## Gaps

The following areas had thin public source coverage. These will need to be supplemented from direct TST observation or Epic developer documentation behind the App Orchard login wall.

1. **Token introspection endpoint behavior** — No public docs on what Epic's introspection endpoint (if it exists at all) returns for expired vs active tokens. Evidence: endpoint not published in well-known config.

2. **Specific rate-limit thresholds** — Exact requests-per-second and per-hour limits for non-bulk endpoints are undocumented publicly. The only confirmed limit is the 24-hour bulk export window. Production caps vary per site.

3. **QuestionnaireResponse write-back** — Epic's support for SDOH QuestionnaireResponse.Create is referenced but specific validation rules, required fields, and error shapes are not publicly documented.

4. **Subscription resource behavior** — Epic's FHIR R4 Subscription implementation (topic-based backport) has no public documentation on supported topics, notification shapes, or channel types. Epic's "event-based interfaces" recommendation suggests Subscription is limited.

5. **Patient.$match operation** — Epic's Patient.$match operation (identity matching) behavior, required input fields, minimum match score, and rejection conditions are not publicly documented. The API spec page returned 404.

6. **Provenance resource write** — Whether Epic accepts or ignores Provenance resources on write operations (create/update) is undocumented. US Core 7.0+ requires Provenance support.

7. **Task resource** — Task resource support for referral workflows and prior auth workflows is referenced in Da Vinci IGs but Epic-specific behavior is not in public sources.

8. **SMART Health Cards / SHLinks** — Epic supports SMART Health Cards for vaccine credentials, but the exact quirks of their SHL implementation and the manifest structure they return are not publicly documented.

9. **Encounter-scoped vs patient-scoped token behavior** — Differences in what data is accessible with an encounter-launch token vs a patient-launch token (beyond standard scope differences) are not quantified in public sources.

10. **Error body format consistency** — Whether Epic consistently returns OperationOutcome vs plain-text or HTML error bodies across all endpoints (especially for 500-level errors) is not confirmed from public sources.

---

## Source Bibliography

| # | URL | Used In |
|---|-----|---------|
| 1 | https://github.com/smart-on-fhir/cumulus/discussions/5 | Q13, Q14, Q15, Q19, Q20, Q21, Q28, Q29, Q36, Q37 |
| 2 | https://github.com/smart-on-fhir/client-js/issues/145 | Q1 |
| 3 | https://github.com/smart-on-fhir/client-js/issues/87 | Q2 |
| 4 | https://github.com/smart-on-fhir/client-js/issues/105 | Q4 |
| 5 | https://docs.intraconnects.com/docs/ehr-basics/epic/Auth/jwt/ | Q7 |
| 6 | https://docs.intraconnects.com/docs/ehr-basics/epic/Auth/Backend/ | Q8 |
| 7 | https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/.well-known/smart-configuration | Q5 |
| 8 | https://groups.google.com/g/smart-on-fhir/c/vtukyF_IO8s | Q6, Q44 |
| 9 | https://groups.google.com/g/smart-on-fhir/c/K7N0dXMZUJc | Q3 |
| 10 | https://chat-archive.fhir.org/stream/179166-implementers/topic/Epic.20Bulk.20Data.20Export.20questions.3F.html | Q35, Q37 |
| 11 | https://chat-archive.fhir.org/stream/179159-cds-hooks/topic/Epic.20CDS.20Hook.20Simulator.3F.html | Q27, Q43 |
| 12 | https://6b.health/insight/epic-fhir-api-integration/ | Q16, Q41 |
| 13 | https://6b.health/insight/exploring-epics-available-fhir-resources-from-appointment-to-allergy-data/ | Q17, Q25, Q26, Q27, Q30, Q40 |
| 14 | https://6b.health/insight/working-with-epic-fhir-sandboxes-production-endpoints-best-practices/ | Q15, Q30, Q31 |
| 15 | https://docs.redoxengine.com/fhir-api-actions/patients/search-for-a-patient-with-identifier/ | Q11, Q22 |
| 16 | https://techcommunity.microsoft.com/blog/healthcareandlifesciencesblog/fhirlink-connector-support-for-epic-on-fhir/4162824 | Q10 |
| 17 | https://fhir.epic.com/Specifications?api=825 | Q17 |
| 18 | https://orbdoc.com/learn/epic-integration-technical-guide/ | Q32, Q39 |
| 19 | https://www.tactionsoft.com/blog/epic-ehr-integration-guide/ | Q12 |
| 20 | https://www.stitchflow.com/user-management/epic/api | Q16 |
| 21 | https://www.emrdirect.com/kb/client-applications/fhir-version-support | Q42 |
| 22 | https://support.interopio.com/hc/en-us/articles/4419488428052-Bulk-Data-Export-in-the-Epic-R4-Gateway | Q38 |
| 23 | https://medium.com/@hanzla1702/epic-fhir-implementing-backend-services-with-smart-oauth-2-0-8bcd8af0c6b0 | Q1 |
| 24 | https://www.mulesoft.com/exchange/org.mule.examples/epic-fhir-r4-medications-api/minor/1.0/pages/Use%20case/ | Q34 |
| 25 | https://www.beckershospitalreview.com/healthcare-information-technology/how-epic-is-adding-patient-gender-identity-to-ehrs-6-things-to-know/ | Q33 |
| 26 | https://fhir.epic.com/Documentation?docId=cds-hooks | Q27, Q43 |
| 27 | https://fhir.epic.com/Documentation | Q18, Q23, Q24 |
| 28 | https://open.epic.com/Clinical/Document | Q24 |
| 29 | https://healthapiguy.substack.com/p/epic-v-particle | Background context |
| 30 | https://www.mindbowser.com/epic-device-integration-hl7-oru-vs-fhir-observation/ | Q39 |
