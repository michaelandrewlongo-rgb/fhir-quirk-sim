from pydantic import BaseModel
from typing import Any


class SanitizedResource(BaseModel):
    resource_type: str
    field_id: str | None = None
    data: dict[str, Any]
    source_ref: str
    is_deidentified: bool = True
    content_text: str | None = None


class SanitizedBundle(BaseModel):
    session_id: str
    resources: list[SanitizedResource]
    errors: list[str] = []
