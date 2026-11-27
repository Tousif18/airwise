"""Regression tests for unambiguous location selection across AirWise APIs."""

from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import app
from app.schemas.assistant import AssistantChatRequest, AssistantRecommendationsRequest
from app.schemas.indoor import IndoorAdvisorRequest
from app.services.locations import resolve_location_selection


@pytest.mark.parametrize("schema", [
    AssistantChatRequest,
    AssistantRecommendationsRequest,
    IndoorAdvisorRequest,
])
def test_request_schemas_reject_partial_coordinates(schema) -> None:
    payload = {"latitude": 22.5726}
    if schema is AssistantChatRequest:
        payload["question"] = "Check air quality"
    with pytest.raises(ValidationError):
        schema(**payload)


@pytest.mark.parametrize("schema", [
    AssistantChatRequest,
    AssistantRecommendationsRequest,
    IndoorAdvisorRequest,
])
def test_request_schemas_reject_preset_and_custom_coordinates_together(schema) -> None:
    payload = {
        "location_id": "kolkata-in",
        "latitude": 22.5726,
        "longitude": 88.3639,
    }
    if schema is AssistantChatRequest:
        payload["question"] = "Check air quality"
    with pytest.raises(ValidationError):
        schema(**payload)


def test_resolver_rejects_partial_coordinates() -> None:
    with pytest.raises(ValueError, match="Both latitude and longitude"):
        resolve_location_selection(latitude=22.5726)


def test_resolver_rejects_preset_and_custom_coordinates_together() -> None:
    with pytest.raises(ValueError, match="either a preset"):
        resolve_location_selection(
            location_id="kolkata-in", latitude=22.5726, longitude=88.3639
        )


def test_resolver_preserves_default_kolkata_selection() -> None:
    location = resolve_location_selection()
    assert location is not None
    assert location.id == "kolkata-in"


def test_resolver_accepts_valid_preset_and_custom_coordinate_selections() -> None:
    preset = resolve_location_selection(location_id="kolkata-in")
    custom = resolve_location_selection(latitude=12.9, longitude=77.5)
    assert preset is not None and preset.id == "kolkata-in"
    assert custom is not None and custom.latitude == 12.9
    assert custom.longitude == 77.5


def test_air_quality_route_rejects_partial_coordinates() -> None:
    response = TestClient(app).get(
        "/api/v1/air-quality", params={"latitude": 22.5726}
    )
    assert response.status_code == 422


def test_air_quality_route_rejects_preset_and_custom_coordinates_together() -> None:
    response = TestClient(app).get(
        "/api/v1/air-quality",
        params={
            "location_id": "kolkata-in",
            "latitude": 22.5726,
            "longitude": 88.3639,
        },
    )
    assert response.status_code == 422


