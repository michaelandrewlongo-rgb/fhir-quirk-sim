import hashlib
import re


class TokenStore:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self._value_to_token: dict[str, str] = {}
        self._token_to_value: dict[str, str] = {}

    def tokenize(self, value: str, phi_type: str) -> str:
        key = f"{phi_type}:{value}"
        if key in self._value_to_token:
            return self._value_to_token[key]
        short_hash = hashlib.sha256(f"{self.session_id}:{key}".encode()).hexdigest()[:8]
        token = f"<<{phi_type}_{short_hash}>>"
        self._value_to_token[key] = token
        self._token_to_value[token] = value
        return token

    def rehydrate(self, text: str) -> str:
        def replace_token(match):
            token = match.group(0)
            return self._token_to_value.get(token, token)

        return re.sub(r"<<[a-z_]+_[a-f0-9]+>>", replace_token, text)

    def redact_known_phi(self, text: str) -> str:
        """
        Replace verbatim occurrences of known PHI values in free-text with their tokens.

        This is used as a second pass after structured de-identification to sanitize
        narrative fields (note, text, description) that may contain PHI strings that
        were already tokenized from structured fields (e.g., a patient name that
        appears in both subject.display and Procedure.note[].text).

        Only PHI values already present in this token store are replaced.  Longer
        values are replaced before shorter ones to avoid partial matches.
        """
        if not text:
            return text
        # Build a mapping from raw PHI value -> token, sorted longest-first to
        # prevent partial replacements (e.g., replace "Alice Marie" before "Alice").
        known_phi: list[tuple[str, str]] = []
        for key, token in self._value_to_token.items():
            # key format is "phi_type:raw_value"
            colon_idx = key.index(":")
            raw_value = key[colon_idx + 1:]
            known_phi.append((raw_value, token))
        known_phi.sort(key=lambda pair: len(pair[0]), reverse=True)

        result = text
        for raw_value, token in known_phi:
            if raw_value and raw_value in result:
                result = result.replace(raw_value, token)
        return result

    @property
    def token_count(self) -> int:
        return len(self._token_to_value)
