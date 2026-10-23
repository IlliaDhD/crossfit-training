from typing import ClassVar

from beanie import Document
from pymongo import ASCENDING, IndexModel

from crosfit_training_backend.api.schemas.complex import ComplexTemplate


class Complex(Document, ComplexTemplate):
    """Complex template (a reusable sequence of sets)."""

    class Settings:
        name = "complexes"
        indexes: ClassVar[list[IndexModel]] = [
            IndexModel([("slug", ASCENDING)], name="slug_unique", unique=True),
            IndexModel([("name", ASCENDING)], name="name"),
        ]
