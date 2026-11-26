"""Household family profile endpoints."""

from threading import Lock
from fastapi import APIRouter

from app.schemas.family import (
    CommuteMethod,
    FamilyProfile,
    SensitivityLevel,
    VentilationPreference,
)

router = APIRouter(prefix="/family", tags=["family"])
legacy_router = APIRouter(prefix="/family-profile", tags=["family"])

_profile_lock = Lock()
_current_profile = FamilyProfile(
    city="Kolkata",
    location_id="kolkata-in",
    location_label="Kolkata, West Bengal, India",
    household_size=4,
    children_count=1,
    elderly_count=0,
    has_respiratory_condition=False,
    respiratory_vulnerability="",
    sensitivity_level=SensitivityLevel.MODERATE,
    commute_method=CommuteMethod.PUBLIC_TRANSIT,
    daily_outdoor_commute=True,
    outdoor_activity_schedule="Morning school commute (7:30-8:30 AM) and late afternoon outdoor time",
    ventilation_preference=VentilationPreference.LOW_SMOG_WINDOWS,
    has_air_purifier=True,
    notes="Prefers indoor ventilation alerts during winter smog inversions.",
)


def get_stored_family_profile() -> FamilyProfile:
    """Return a thread-safe copy of the stored household profile."""
    with _profile_lock:
        return _current_profile.model_copy()


def save_stored_family_profile(profile: FamilyProfile) -> FamilyProfile:
    """Persist and return a thread-safe copy of the updated household profile."""
    global _current_profile
    with _profile_lock:
        _current_profile = profile.model_copy()
        return _current_profile.model_copy()


@router.get("/profile", response_model=FamilyProfile)
async def get_family_profile() -> FamilyProfile:
    """Return current household profile configuration."""
    return get_stored_family_profile()


@router.put("/profile", response_model=FamilyProfile)
async def update_family_profile(profile: FamilyProfile) -> FamilyProfile:
    """Update household profile configuration."""
    return save_stored_family_profile(profile)


@legacy_router.get("", response_model=FamilyProfile, include_in_schema=False)
async def get_legacy_family_profile() -> FamilyProfile:
    """Legacy Phase 1 alias for GET /api/v1/family/profile."""
    return get_stored_family_profile()


@legacy_router.put("", response_model=FamilyProfile, include_in_schema=False)
async def update_legacy_family_profile(profile: FamilyProfile) -> FamilyProfile:
    """Legacy Phase 1 alias for PUT /api/v1/family/profile."""
    return save_stored_family_profile(profile)
