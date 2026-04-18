from pydantic import BaseModel, field_validator


class FetchPlanItem(BaseModel):
    resource_type: str
    codes: list[str] | None = None
    category: str | None = None
    time_window_hours: int | None = None
    limit: int | None = None


class FetchPlan(BaseModel):
    session_id: str
    patient_id: str
    encounter_id: str | None = None
    items: list[FetchPlanItem]

    @field_validator("items")
    @classmethod
    def at_least_one_item(cls, v):
        if len(v) == 0:
            raise ValueError("Fetch plan must contain at least one item")
        return v
