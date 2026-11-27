"""Regression tests for timezone validation in location request schemas."""

from pathlib import Path
import sys

import pytest
from pydantic import ValidationError

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.schemas.assistant import AssistantChatRequest, AssistantRecommendationsRequest
from app.schemas.indoor import IndoorAdvisorRequest


@pytest.mark.parametrize("timezone", ["auto", "Asia/Kolkata", "Europe/London", "UTC"])
def test_assistant_requests_accept_valid_timezones(timezone: str) -> None:
    payload = AssistantChatRequest(question="Check air quality", timezone=timezone)
    assert payload.timezone == timezone


@pytest.mark.parametrize("timezone", ["auto", "Asia/Kolkata", "UTC"])
def test_recommendation_requests_accept_valid_timezones(timezone: str) -> None:
    payload = AssistantRecommendationsRequest(timezone=timezone)
    assert payload.timezone == timezone


@pytest.mark.parametrize("timezone", ["auto", "Asia/Kolkata", "Europe/London", "UTC"])
def test_indoor_requests_accept_valid_timezones(timezone: str) -> None:
    payload = IndoorAdvisorRequest(timezone=timezone)
    assert payload.timezone == timezone


@pytest.mark.parametrize(
    "timezone",
    ["Mars/Olympus", "Not_A_Timezone", "", "   ", "../etc/passwd"],
)
@pytest.mark.parametrize(
    "schema",
    [AssistantChatRequest, AssistantRecommendationsRequest, IndoorAdvisorRequest],
)
def test_location_requests_reject_invalid_timezones(schema, timezone: str) -> None:
    kwargs = {"timezone": timezone}
    if schema is AssistantChatRequest:
        kwargs["question"] = "Check air quality"
    with pytest.raises(ValidationError):
        schema(**kwargs)


def test_assistant_timezone_validator_normalizes_surrounding_whitespace() -> None:
    payload = AssistantRecommendationsRequest(timezone=" Asia/Kolkata ")
    assert payload.timezone == "Asia/Kolkata"
