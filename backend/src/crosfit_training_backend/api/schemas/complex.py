"""Complex templates (data-model.md, sections 7.1, 9.6)."""

from uuid import UUID

from beanie import PydanticObjectId
from pydantic import BaseModel, ConfigDict, Field

from crosfit_training_backend.api.schemas.exercise import ExerciseName, Slug
from crosfit_training_backend.api.schemas.sets import SetIn
from crosfit_training_backend.api.schemas.training import SectionFormat


class ComplexTemplate(BaseModel):
    """Stored template. `items` use the set models, so nested complexes are
    impossible: a `complex` item does not pass the `SetIn` discriminator (422)."""

    name: ExerciseName
    slug: Slug
    tags: list[str] = Field(default_factory=list)
    format: SectionFormat = "standard"
    rounds: int | None = Field(None, gt=0)
    time_cap: int | None = Field(None, gt=0, description="seconds")
    items: list[SetIn] = Field(min_length=1)
    owner_id: UUID | None = Field(
        None, description="Keycloak `sub` of the owner; null means a global template"
    )
    is_archived: bool = False


class ComplexIn(BaseModel):
    name: ExerciseName
    slug: Slug
    tags: list[str] = Field(default_factory=list)
    format: SectionFormat = "standard"
    rounds: int | None = Field(None, gt=0)
    time_cap: int | None = Field(None, gt=0, description="seconds")
    items: list[SetIn] = Field(min_length=1)
    is_global: bool = Field(
        False, description="Global template visible to everyone. Admin only."
    )


class ComplexOut(ComplexTemplate):
    model_config = ConfigDict(from_attributes=True)

    id: PydanticObjectId


class ComplexListOut(BaseModel):
    items: list[ComplexOut]
    total: int
    limit: int
    offset: int
