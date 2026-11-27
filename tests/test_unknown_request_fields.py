"""Regression tests for rejecting unknown request fields."""

from pathlib import Path
import sys

import pytest
from pydantic import ValidationError

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.schemas.assistant import AssistantChatRequest, AssistantRecommendationsRequest
from app.schemas.family import FamilyProfile
from app.schemas.indoor import HomeEnvironmentProfile, IndoorAdvisorRequest


def test_assistant_request_rejects_unknown_top_level_field() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        AssistantChatRequest(question="Check air quality", time_zone="Asia/Kolkata")


def test_recommendations_request_rejects_unknown_top_level_field() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        AssistantRecommendationsRequest(unexpected_option=True)


def test_family_profile_rejects_unknown_nested_field() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        AssistantChatRequest(
            question="Check air quality",
            family_profile={"household_size": 3, "unknown_preference": "value"},
        )


def test_home_environment_rejects_unknown_nested_field() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        IndoorAdvisorRequest(
            home_environment={"room_count": 3, "purifier_type": "HEPA"},
        )


def test_legacy_family_profile_fields_remain_supported() -> None:
    profile = FamilyProfile(member_count=3, has_hepa_purifier=False)
    assert profile.household_size == 3
    assert profile.has_air_purifier is False


def test_normal_assistant_and_indoor_payloads_remain_valid() -> None:
    assistant = AssistantChatRequest(
        question="Check air quality",
        location_id="kolkata-in",
        family_profile={"household_size": 3, "children_count": 1},
    )
    indoor = IndoorAdvisorRequest(
        location_id="kolkata-in",
        home_environment={"room_count": 2, "has_air_purifier": True},
    )
    assert assistant.location_id == "kolkata-in"
    assert indoor.home_environment.room_count == 2
