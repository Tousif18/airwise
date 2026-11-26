"""Unit tests for Indian CPCB NAQI breakpoint calculations and adequacy rules."""

from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.schemas.air_quality import DataStatus
from app.services.cpcb_aqi import (
    calculate_cpcb_sub_index,
    classify_cpcb_aqi,
    compute_cpcb_aqi_from_averages,
    compute_cpcb_aqi_from_hourly,
)


def test_cpcb_sub_index_breakpoint_bands() -> None:
    # Exact boundaries and midpoints for PM2.5
    assert calculate_cpcb_sub_index("pm2_5", 0.0) == 0
    assert calculate_cpcb_sub_index("pm2_5", 30.0) == 50
    assert calculate_cpcb_sub_index("pm2_5", 45.0) == 75
    assert calculate_cpcb_sub_index("pm2_5", 90.0) == 200
    assert calculate_cpcb_sub_index("pm2_5", 185.0) == 350
    assert calculate_cpcb_sub_index("pm2_5", 315.0) == 450
    assert calculate_cpcb_sub_index("pm2_5", 600.0) == 500  # Capped at 500
    assert calculate_cpcb_sub_index("pm2_5", -1.0) is None
    assert calculate_cpcb_sub_index("pm2_5", None) is None

    # CO in mg/m3 (0-1 -> 0-50, 1-2 -> 50-100, 2-10 -> 100-200)
    assert calculate_cpcb_sub_index("carbon_monoxide", 1.0) == 50
    assert calculate_cpcb_sub_index("carbon_monoxide", 6.0) == 150


def test_cpcb_categories() -> None:
    assert classify_cpcb_aqi(42) == "Good"
    assert classify_cpcb_aqi(85) == "Satisfactory"
    assert classify_cpcb_aqi(175) == "Moderate"
    assert classify_cpcb_aqi(260) == "Poor"
    assert classify_cpcb_aqi(360) == "Very Poor"
    assert classify_cpcb_aqi(450) == "Severe"
    assert classify_cpcb_aqi(None) == "Unavailable"


def test_cpcb_composite_max_sub_index_and_prominent_pollutant() -> None:
    summary = compute_cpcb_aqi_from_averages(
        averaged_concentrations={
            "pm2_5": (90.0, 24),          # sub-index 200 (Moderate)
            "pm10": (300.0, 24),          # sub-index 250 (Poor) -> dominant
            "nitrogen_dioxide": (40.0, 24),  # sub-index 50 (Good)
            "ozone": (50.0, 8),           # sub-index 50 (Good)
        }
    )

    assert summary.status == DataStatus.LIVE
    assert summary.aqi == 250
    assert summary.category == "Poor"
    assert summary.prominent_pollutant == "PM10"
    assert summary.prominent_pollutant_key == "pm10"
    assert summary.valid_pollutant_count == 4
    assert summary.unavailable_reason is None


def test_cpcb_requires_minimum_three_pollutants() -> None:
    summary = compute_cpcb_aqi_from_averages(
        averaged_concentrations={
            "pm2_5": (85.0, 24),
            "pm10": (140.0, 24),
        }
    )

    assert summary.status == DataStatus.UNAVAILABLE
    assert summary.aqi is None
    assert summary.category == "Unavailable"
    assert "minimum 3 pollutants" in (summary.unavailable_reason or "")


def test_cpcb_requires_particulate_matter() -> None:
    # 4 gaseous pollutants without PM2.5 or PM10 must still be Unavailable
    summary = compute_cpcb_aqi_from_averages(
        averaged_concentrations={
            "nitrogen_dioxide": (60.0, 24),
            "ozone": (80.0, 8),
            "carbon_monoxide": (1.5, 8),
            "sulphur_dioxide": (40.0, 24),
        }
    )

    assert summary.status == DataStatus.UNAVAILABLE
    assert summary.aqi is None
    assert "PM2.5 or PM10" in (summary.unavailable_reason or "")


def test_cpcb_hourly_enforces_valid_hour_minimums_and_co_conversion() -> None:
    # 24 hours of valid PM2.5, NO2, and 8 hours of CO (in ug/m3 -> mg/m3)
    hourly_valid = {
        "pm2_5": [60.0] * 24,            # 24h avg = 60 -> sub-index 100
        "nitrogen_dioxide": [40.0] * 24, # 24h avg = 40 -> sub-index 50
        "carbon_monoxide": [2000.0] * 24, # 8h avg = 2.0 mg/m3 -> sub-index 100
    }
    valid_res = compute_cpcb_aqi_from_hourly(hourly_valid, past_slice_end=24)
    assert valid_res.status == DataStatus.LIVE
    assert valid_res.aqi == 100
    assert valid_res.category == "Satisfactory"

    # Only 12 valid hours for PM2.5 (< 16 required) -> drops PM2.5 -> Unavailable
    hourly_insufficient = {
        "pm2_5": [None] * 12 + [60.0] * 12,
        "nitrogen_dioxide": [40.0] * 24,
        "ozone": [50.0] * 24,
        "carbon_monoxide": [1000.0] * 24,
    }
    insufficient_res = compute_cpcb_aqi_from_hourly(hourly_insufficient, past_slice_end=24)
    assert insufficient_res.status == DataStatus.UNAVAILABLE
    assert insufficient_res.aqi is None
