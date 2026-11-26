"""Pydantic schemas for household family profiles and sensitivity settings."""

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, model_validator


class SensitivityLevel(str, Enum):
    """Household respiratory sensitivity tier."""

    STANDARD = "standard"
    MODERATE = "moderate"
    HIGH = "high"


class CommuteMethod(str, Enum):
    """Primary daily household commute mode."""

    WALKING = "walking"
    CYCLING = "cycling"
    TWO_WHEELER = "two_wheeler"
    PUBLIC_TRANSIT = "public_transit"
    CAR_OR_CAB = "car_or_cab"
    WORK_FROM_HOME = "work_from_home"
    MIXED = "mixed"


class VentilationPreference(str, Enum):
    """Preferred indoor home ventilation strategy."""

    NATURAL_CROSS_VENTILATION = "natural_cross_ventilation"
    LOW_SMOG_WINDOWS = "low_smog_windows"
    SEALED_WITH_FILTRATION = "sealed_with_filtration"
    MINIMAL_OPENING = "minimal_opening"


class FamilyProfile(BaseModel):
    """Configurable household profile used to tailor AirWise guidance.

    Intentionally excludes personal names, medical records, and sensitive PII.
    """

    city: str = Field(default="Kolkata", min_length=1, max_length=100)
    location_id: str | None = Field(default="kolkata-in", max_length=80)
    location_label: str = Field(default="Kolkata, West Bengal, India", max_length=160)
    household_size: int = Field(default=4, ge=1, le=20)
    children_count: int = Field(default=1, ge=0, le=20)
    elderly_count: int = Field(default=0, ge=0, le=20)
    has_respiratory_condition: bool = False
    respiratory_vulnerability: str = Field(default="", max_length=200)
    sensitivity_level: SensitivityLevel = SensitivityLevel.MODERATE
    commute_method: CommuteMethod = CommuteMethod.PUBLIC_TRANSIT
    daily_outdoor_commute: bool = True
    outdoor_activity_schedule: str = Field(
        default="Morning school commute (7:30-8:30 AM) and late afternoon outdoor time",
        max_length=240,
    )
    ventilation_preference: VentilationPreference = VentilationPreference.LOW_SMOG_WINDOWS
    has_air_purifier: bool = True
    notes: str = Field(default="", max_length=280)

    # Legacy compatibility fields synchronized with canonical fields above.
    household_name: str | None = Field(default=None, max_length=80)
    member_count: int | None = Field(default=None, ge=1, le=20)
    has_young_children: bool | None = None
    has_older_adults: bool | None = None
    has_hepa_purifier: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_inputs(cls, data: Any) -> Any:
        """Accept both Phase 1 and Phase 2 field names seamlessly."""
        if not isinstance(data, dict):
            return data
        normalized = dict(data)

        if "household_size" not in normalized and normalized.get("member_count") is not None:
            normalized["household_size"] = normalized["member_count"]

        if "has_air_purifier" not in normalized and normalized.get("has_hepa_purifier") is not None:
            normalized["has_air_purifier"] = normalized["has_hepa_purifier"]

        if "children_count" not in normalized and normalized.get("has_young_children") is True:
            normalized["children_count"] = 1

        if "elderly_count" not in normalized and normalized.get("has_older_adults") is True:
            normalized["elderly_count"] = 1

        for str_field in ("city", "location_label", "respiratory_vulnerability", "outdoor_activity_schedule", "notes"):
            if isinstance(normalized.get(str_field), str):
                normalized[str_field] = normalized[str_field].strip()

        return normalized

    @model_validator(mode="after")
    def validate_and_sync_household_counts(self) -> "FamilyProfile":
        """Ensure dependent counts never exceed household size and sync aliases."""
        if self.children_count + self.elderly_count > self.household_size:
            raise ValueError(
                "children_count + elderly_count cannot exceed household_size."
            )

        self.member_count = self.household_size
        self.has_young_children = self.children_count > 0
        self.has_older_adults = self.elderly_count > 0
        self.has_hepa_purifier = self.has_air_purifier
        if self.commute_method == CommuteMethod.WORK_FROM_HOME:
            self.daily_outdoor_commute = False
        return self


# Backward-compatible alias for existing Phase 1 imports
HouseholdProfile = FamilyProfile
