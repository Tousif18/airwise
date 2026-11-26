"""Pydantic schemas for household family profiles and sensitivity settings."""

from enum import Enum
from pydantic import BaseModel, Field


class SensitivityLevel(str, Enum):
    """Household respiratory sensitivity tier."""

    STANDARD = "standard"
    MODERATE = "moderate"
    HIGH = "high"


class HouseholdProfile(BaseModel):
    """Configurable household profile used to tailor AirWise guidance."""

    household_name: str = Field(default="My Household", min_length=1, max_length=80)
    member_count: int = Field(default=4, ge=1, le=20)
    has_young_children: bool = False
    has_older_adults: bool = False
    has_respiratory_condition: bool = False
    daily_outdoor_commute: bool = True
    has_hepa_purifier: bool = False
    sensitivity_level: SensitivityLevel = SensitivityLevel.MODERATE
    notes: str = Field(default="", max_length=280)
