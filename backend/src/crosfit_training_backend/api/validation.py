"""Shared HTTP query validation."""

import datetime as dt

from fastapi import HTTPException


def validate_dates(date_from: dt.date | None, date_to: dt.date | None) -> None:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must be <= date_to")
