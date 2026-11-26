"""Indian CPCB National Air Quality Index (NAQI) breakpoint calculator.

Implements the official CPCB segmented linear interpolation methodology across
available pollutants, enforcing the minimum 3-pollutant and particulate-presence
adequacy requirements without converting from US AQI.
"""

from dataclasses import dataclass
from typing import Iterable

from app.schemas.air_quality import (
    CPCBSubIndex,
    DataStatus,
    IndianAQISummary,
    ValueKind,
)

# (BP_LO, BP_HI, I_LO, I_HI) continuous breakpoint segments for CPCB NAQI
CPCB_BREAKPOINTS: dict[str, list[tuple[float, float, int, int]]] = {
    "pm2_5": [
        (0.0, 30.0, 0, 50),
        (30.0, 60.0, 50, 100),
        (60.0, 90.0, 100, 200),
        (90.0, 120.0, 200, 300),
        (120.0, 250.0, 300, 400),
        (250.0, 380.0, 400, 500),
    ],
    "pm10": [
        (0.0, 50.0, 0, 50),
        (50.0, 100.0, 50, 100),
        (100.0, 250.0, 100, 200),
        (250.0, 350.0, 200, 300),
        (350.0, 430.0, 300, 400),
        (430.0, 510.0, 400, 500),
    ],
    "nitrogen_dioxide": [
        (0.0, 40.0, 0, 50),
        (40.0, 80.0, 50, 100),
        (80.0, 180.0, 100, 200),
        (180.0, 280.0, 200, 300),
        (280.0, 400.0, 300, 400),
        (400.0, 520.0, 400, 500),
    ],
    "ozone": [
        (0.0, 50.0, 0, 50),
        (50.0, 100.0, 50, 100),
        (100.0, 168.0, 100, 200),
        (168.0, 208.0, 200, 300),
        (208.0, 748.0, 300, 400),
        (748.0, 1288.0, 400, 500),
    ],
    # CPCB CO breakpoints are in mg/m³ (8-hr average)
    "carbon_monoxide": [
        (0.0, 1.0, 0, 50),
        (1.0, 2.0, 50, 100),
        (2.0, 10.0, 100, 200),
        (10.0, 17.0, 200, 300),
        (17.0, 34.0, 300, 400),
        (34.0, 51.0, 400, 500),
    ],
    "sulphur_dioxide": [
        (0.0, 40.0, 0, 50),
        (40.0, 80.0, 50, 100),
        (80.0, 380.0, 100, 200),
        (380.0, 800.0, 200, 300),
        (800.0, 1600.0, 300, 400),
        (1600.0, 2400.0, 400, 500),
    ],
}


@dataclass(frozen=True)
class CPCBParameterMeta:
    """Averaging window and unit specification for a CPCB AQI pollutant."""

    formula: str
    unit: str
    averaging_period: str
    window_hours: int
    min_valid_hours: int
    scale_from_ug_m3: float = 1.0


CPCB_PARAMETERS: dict[str, CPCBParameterMeta] = {
    "pm2_5": CPCBParameterMeta("PM2.5", "μg/m³", "24-hr avg", 24, 16),
    "pm10": CPCBParameterMeta("PM10", "μg/m³", "24-hr avg", 24, 16),
    "nitrogen_dioxide": CPCBParameterMeta("NO₂", "μg/m³", "24-hr avg", 24, 16),
    "ozone": CPCBParameterMeta("O₃", "μg/m³", "8-hr avg", 8, 6),
    "carbon_monoxide": CPCBParameterMeta(
        "CO", "mg/m³", "8-hr avg", 8, 6, scale_from_ug_m3=0.001
    ),
    "sulphur_dioxide": CPCBParameterMeta("SO₂", "μg/m³", "24-hr avg", 24, 16),
}


def classify_cpcb_aqi(aqi: int | float | None) -> str:
    """Map Indian CPCB AQI numeric value to official 6-tier category."""
    if aqi is None:
        return "Unavailable"
    if aqi <= 50:
        return "Good"
    if aqi <= 100:
        return "Satisfactory"
    if aqi <= 200:
        return "Moderate"
    if aqi <= 300:
        return "Poor"
    if aqi <= 400:
        return "Very Poor"
    return "Severe"


def calculate_cpcb_sub_index(pollutant_key: str, concentration: float | None) -> int | None:
    """Calculate CPCB sub-index via segmented linear interpolation, capped at 500."""
    if concentration is None or concentration < 0:
        return None
    segments = CPCB_BREAKPOINTS.get(pollutant_key)
    if not segments:
        return None

    for bp_lo, bp_hi, i_lo, i_hi in segments:
        if concentration <= bp_hi:
            if bp_hi == bp_lo:
                return i_hi
            sub_index = ((i_hi - i_lo) / (bp_hi - bp_lo)) * (concentration - bp_lo) + i_lo
            return min(500, max(0, int(round(sub_index))))

    # Above upper Severe ceiling: official CPCB index is capped at 500
    return 500


def compute_cpcb_aqi_from_averages(
    averaged_concentrations: dict[str, tuple[float, int]],
    data_status: DataStatus = DataStatus.LIVE,
    value_kind: ValueKind = ValueKind.ESTIMATED,
) -> IndianAQISummary:
    """Compute Indian CPCB AQI from pre-averaged concentrations.

    `averaged_concentrations` maps pollutant_key -> (concentration_in_cpcb_unit, valid_hours).
    Enforces the CPCB rule: at least 3 valid pollutants AND at least one of PM2.5 or PM10.
    """
    sub_indices: list[CPCBSubIndex] = []
    for key, meta in CPCB_PARAMETERS.items():
        if key not in averaged_concentrations:
            continue
        conc, valid_hours = averaged_concentrations[key]
        if valid_hours < meta.min_valid_hours:
            continue
        sub_val = calculate_cpcb_sub_index(key, conc)
        if sub_val is None:
            continue
        sub_indices.append(
            CPCBSubIndex(
                pollutant_key=key,
                formula=meta.formula,
                concentration=round(conc, 2),
                unit=meta.unit,
                averaging_period=meta.averaging_period,
                valid_hours=valid_hours,
                required_hours=meta.window_hours,
                sub_index=sub_val,
                category=classify_cpcb_aqi(sub_val),
            )
        )

    valid_keys = {item.pollutant_key for item in sub_indices}
    has_particulate = bool(valid_keys & {"pm2_5", "pm10"})
    valid_count = len(sub_indices)

    if valid_count < 3 or not has_particulate:
        missing_reasons: list[str] = []
        if not has_particulate:
            missing_reasons.append(
                "at least one particulate metric (PM2.5 or PM10 with >=16h data) is required"
            )
        if valid_count < 3:
            missing_reasons.append(
                f"minimum 3 pollutants with adequate averaging windows required (found {valid_count})"
            )
        return IndianAQISummary(
            aqi=None,
            category="Unavailable",
            status=DataStatus.UNAVAILABLE,
            valid_pollutant_count=valid_count,
            sub_indices=sub_indices,
            value_kind=value_kind,
            unavailable_reason="Indian CPCB AQI unavailable: " + "; ".join(missing_reasons) + ".",
        )

    dominant = max(sub_indices, key=lambda item: item.sub_index)
    return IndianAQISummary(
        aqi=dominant.sub_index,
        category=classify_cpcb_aqi(dominant.sub_index),
        status=data_status,
        prominent_pollutant=dominant.formula,
        prominent_pollutant_key=dominant.pollutant_key,
        valid_pollutant_count=valid_count,
        sub_indices=sub_indices,
        value_kind=value_kind,
        unavailable_reason=None,
    )


def compute_cpcb_aqi_from_hourly(
    hourly_series: dict[str, Iterable[float | None]],
    past_slice_end: int,
    data_status: DataStatus = DataStatus.LIVE,
    value_kind: ValueKind = ValueKind.ESTIMATED,
) -> IndianAQISummary:
    """Compute Indian CPCB AQI using trailing 24h/8h windows ending at `past_slice_end`."""
    averaged: dict[str, tuple[float, int]] = {}
    end_idx = max(0, past_slice_end)

    for key, meta in CPCB_PARAMETERS.items():
        series = list(hourly_series.get(key) or [])
        if not series or end_idx == 0:
            continue
        start_idx = max(0, end_idx - meta.window_hours)
        window_values = [
            float(val) * meta.scale_from_ug_m3
            for val in series[start_idx:end_idx]
            if val is not None and float(val) >= 0
        ]
        if len(window_values) >= meta.min_valid_hours:
            averaged[key] = (sum(window_values) / len(window_values), len(window_values))

    return compute_cpcb_aqi_from_averages(
        averaged_concentrations=averaged,
        data_status=data_status,
        value_kind=value_kind,
    )
