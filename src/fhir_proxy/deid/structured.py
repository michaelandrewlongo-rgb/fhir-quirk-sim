from typing import Any
from fhir_proxy.deid.token_store import TokenStore

PHI_FIELDS = {"name", "birthDate", "deceasedDateTime", "address", "telecom"}
IDENTIFIER_FIELDS = {"identifier"}

# FHIR fields that carry free-text narrative content and may contain PHI
# (name, date, etc.) embedded in prose.  After the structured pass tokenizes
# known PHI values into the token store, these fields are scanned for any
# stored PHI values and those occurrences are replaced with their tokens.
FREETEXT_NARRATIVE_FIELDS = {"text", "note", "comment", "description", "conclusion"}


class StructuredDeidentifier:
    def __init__(self, token_store: TokenStore):
        self.token_store = token_store

    def deidentify(self, resource: dict[str, Any]) -> dict[str, Any]:
        # First pass: tokenize all structured PHI fields (name, DOB, display, etc.)
        result = self._process(resource, is_root=True)
        # Second pass: replace any known PHI values found in free-text narrative
        # fields using the token store that was populated during the first pass.
        result = self._redact_freetext_fields(result)
        return result

    def _process(self, obj, is_root=False, key=""):
        if isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                if is_root and k in PHI_FIELDS:
                    result[k] = self._tokenize_phi_field(k, v)
                elif is_root and k in IDENTIFIER_FIELDS:
                    result[k] = self._tokenize_identifiers(v)
                elif k == "display" and isinstance(v, str) and self._looks_like_name(v):
                    result[k] = self.token_store.tokenize(v, "patient_name")
                else:
                    result[k] = self._process(v, is_root=False, key=k)
            return result
        elif isinstance(obj, list):
            return [self._process(item, is_root=False, key=key) for item in obj]
        return obj

    def _redact_freetext_fields(self, obj: Any, parent_key: str = "") -> Any:
        """
        Walk the de-identified resource and replace known PHI values (already in
        the token store) that appear verbatim in free-text narrative fields.

        This handles FHIR fields like Procedure.note[].text and DocumentReference
        content where patient names, dates, or identifiers may appear in prose.
        """
        if isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                if k in FREETEXT_NARRATIVE_FIELDS:
                    result[k] = self._redact_freetext_value(v)
                else:
                    result[k] = self._redact_freetext_fields(v, parent_key=k)
            return result
        elif isinstance(obj, list):
            return [self._redact_freetext_fields(item, parent_key=parent_key) for item in obj]
        return obj

    def _redact_freetext_value(self, value: Any) -> Any:
        """Apply known-PHI replacement to a free-text field value (string or nested structure)."""
        if isinstance(value, str):
            return self.token_store.redact_known_phi(value)
        elif isinstance(value, dict):
            return {k: self._redact_freetext_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._redact_freetext_value(item) for item in value]
        return value

    def _tokenize_phi_field(self, field_name, value):
        if field_name == "name" and isinstance(value, list):
            tokenized = []
            for name_obj in value:
                t = {}
                if "family" in name_obj:
                    t["family"] = self.token_store.tokenize(name_obj["family"], "family_name")
                if "given" in name_obj:
                    t["given"] = [self.token_store.tokenize(g, "given_name") for g in name_obj["given"]]
                tokenized.append(t)
            return tokenized
        elif field_name == "birthDate" and isinstance(value, str):
            return self.token_store.tokenize(value, "birth_date")
        elif field_name in ("address", "telecom"):
            return self.token_store.tokenize(str(value), field_name)
        return self.token_store.tokenize(str(value), field_name)

    def _tokenize_identifiers(self, identifiers):
        if not isinstance(identifiers, list):
            return []
        result = []
        for ident in identifiers:
            tokenized = dict(ident)
            if "value" in tokenized:
                tokenized["value"] = self.token_store.tokenize(tokenized["value"], "mrn")
            result.append(tokenized)
        return result

    def _looks_like_name(self, value: str) -> bool:
        parts = value.strip().split()
        if len(parts) < 2 or len(parts) > 5:
            return False
        return all(p[0].isupper() and p.isalpha() for p in parts)
