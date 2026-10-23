from pydantic import BaseModel, Field


class WeeklyTonnageOut(BaseModel):
    year: int = Field(description="ISO week-numbering year")
    week: int = Field(description="ISO week number")
    movement_pattern: str | None
    tonnage: float = Field(description="sum of reps * weight, kilograms")
    sets: int
