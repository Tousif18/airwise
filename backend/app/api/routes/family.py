"""Household family profile endpoints."""

from threading import Lock
from fastapi import APIRouter

from app.schemas.family import HouseholdProfile, SensitivityLevel

router = APIRouter(prefix="/family-profile", tags=["family-profile"])

_profile_lock = Lock()
_current_profile = HouseholdProfile(
    household_name="Urban Family Household",
    member_count=4,
    has_young_children=True,
    has_older_adults=False,
    has_respiratory_condition=False,
    daily_outdoor_commute=True,
    has_hepa_purifier=True,
    sensitivity_level=SensitivityLevel.MODERATE,
    notes="School commute at 8:00 AM; prefers indoor ventilation alerts.",
)


@router.get("", response_model=HouseholdProfile)
async def get_family_profile() -> HouseholdProfile:
    """Return current household profile configuration."""
    with _profile_lock:
        return _current_profile.model_copy()


@router.put("", response_model=HouseholdProfile)
async def update_family_profile(profile: HouseholdProfile) -> HouseholdProfile:
    """Update household profile configuration."""
    global _current_profile
    with _profile_lock:
        _current_profile = profile.model_copy()
        return _current_profile.model_copy()
