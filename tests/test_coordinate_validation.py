"""Regression tests for finite and in-range geographic coordinates."""

from pathlib import Path
import sys

import pytest
from pydantic import ValidationError

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.schemas.air_quality import LocationOption
from app.schemas.assistant import AssistantChatRequest, AssistantRecommendationsRequest
from app.schemas.indoor import IndoorAdvisorRequest


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [
        (0, 0),
        (90, 180),
        (-90, -180),
        (22.5726, 88.3639),
    ],
)
def test_location_option_accepts_valid_coordinates(latitude, longitude) -> None:
    location = LocationOption(
        id="test", name="Test", country="Test",
        latitude=latitude, longitude=longitude,
    )
    assert location.latitude == latitude
    assert location.longitude == longitude


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [
        (float("nan"), 0),
        (float("inf"), 0),
        (float("-inf"), 0),
        (0, float("nan")),
        (0, float("inf")),
        (0, float("-inf")),
        (90.0001, 0),
        (-90.0001, 0),
        (0, 180.0001),
        (0, -180.0001),
    ],
)
def test_location_option_rejects_non_finite_or_out_of_range_coordinates(
    latitude, longitude
) -> None:
    with pytest.raises(ValidationError):
        LocationOption(
            id="test", name="Test", country="Test",
            latitude=latitude, longitude=longitude,
        )


@pytest.mark.parametrize(
    "schema",
    [AssistantChatRequest, AssistantRecommendationsRequest, IndoorAdvisorRequest],
)
@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [
        (float("nan"), 10),
        (float("inf"), 10),
        (float("-inf"), 10),
        (10, float("nan")),
        (10, float("inf")),
        (10, float("-inf")),
    ],
)
def test_location_requests_reject_non_finite_coordinates(
    schema, latitude, longitude
) -> None:
    payload = {"latitude": latitude, "longitude": longitude}
    if schema is AssistantChatRequest:
        payload["question"] = "Check air quality"
    with pytest.raises(ValidationError):
        schema(**payload)


@pytest.mark.parametrize(
    "schema",
    [AssistantChatRequest, AssistantRecommendationsRequest, IndoorAdvisorRequest],
)
def test_location_requests_accept_coordinate_boundaries(schema) -> None:
    payload = {"latitude": 90, "longitude": 180}
    if schema is AssistantChatRequest:
        payload["question"] = "Check air quality"
    request = schema(**payload)
    assert request.latitude == 90
    assert request.longitude == 180
