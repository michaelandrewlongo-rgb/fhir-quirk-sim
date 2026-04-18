"""Launch context carried by authorization codes and access tokens."""
from pydantic import BaseModel


class LaunchContext(BaseModel):
    patient: str | None = None
    encounter: str | None = None
    fhir_user: str | None = None  # e.g. "Practitioner/prac-001"

    def to_token_extras(self) -> dict:
        """Return SMART launch-context fields to merge into a token response."""
        extras: dict[str, str] = {}
        if self.patient:
            extras["patient"] = self.patient
        if self.encounter:
            extras["encounter"] = self.encounter
        return extras
