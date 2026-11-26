"""Context builder combining location, Open-Meteo data, family profile, and decision rules."""

from typing import Any

from app.schemas.air_quality import AirQualityOverviewResponse, DataStatus, ValueKind
from app.schemas.assistant import ChatTurn
from app.schemas.family import FamilyProfile
from app.services.decision_engine import DecisionAssessment, classify_european_aqi


def build_ai_context(
    air_quality: AirQualityOverviewResponse,
    profile: FamilyProfile,
    assessment: DecisionAssessment,
    question: str | None = None,
    focus_area: str = "daily_plan",
    conversation_history: list[ChatTurn] | None = None,
) -> dict[str, Any]:
    """Assemble transparent, anti-hallucination structured context for Gemini.

    Explicitly separates observed data, atmospheric model estimates, forecast hours,
    and missing data, and excludes personal names or medical records.
    """
    observed_available = air_quality.telemetry_kind == ValueKind.OBSERVED and assessment.air_quality_available
    estimated_pollutants = [
        {
            "key": p.key,
            "formula": p.formula,
            "value": p.value,
            "unit": p.unit,
            "who_24h_guideline": p.guideline_24h,
            "status": p.status.value,
            "value_kind": p.value_kind.value,
            "cpcb_sub_index": p.cpcb_sub_index,
            "cpcb_category": p.cpcb_category,
            "cpcb_averaging_period": p.cpcb_averaging_period,
        }
        for p in air_quality.pollutants
        if p.value is not None
    ]
    missing_pollutants = [
        {"key": p.key, "formula": p.formula, "status": "missing_or_unavailable"}
        for p in air_quality.pollutants
        if p.value is None
    ]

    forecast_points = [
        {
            "time": pt.time,
            "us_aqi": pt.us_aqi,
            "pm2_5_ug_m3": pt.pm2_5,
            "pm10_ug_m3": pt.pm10,
            "value_kind": pt.value_kind.value,
        }
        for pt in air_quality.hourly_trend
        if pt.value_kind == ValueKind.FORECAST
    ][:8]

    aqi_standards = {
        "us_aqi_epa_scale": {
            "available": air_quality.us_aqi is not None,
            "value": air_quality.us_aqi,
            "category": air_quality.aqi_category,
            "value_kind": air_quality.telemetry_kind.value if air_quality.us_aqi is not None else "missing",
        },
        "european_aqi_eaqi": {
            "available": air_quality.european_aqi is not None,
            "value": air_quality.european_aqi,
            "category": classify_european_aqi(air_quality.european_aqi),
            "value_kind": air_quality.telemetry_kind.value if air_quality.european_aqi is not None else "missing",
        },
        "indian_cpcb_naqi": {
            "available": air_quality.indian_aqi.aqi is not None,
            "value": air_quality.indian_aqi.aqi,
            "category": air_quality.indian_aqi.category,
            "prominent_pollutant": air_quality.indian_aqi.prominent_pollutant,
            "value_kind": air_quality.indian_aqi.value_kind.value if air_quality.indian_aqi.aqi is not None else "missing",
            "unavailable_reason": air_quality.indian_aqi.unavailable_reason,
            "note": "Computed independently from CPCB breakpoints; NEVER convert from US AQI or invent if unavailable.",
        },
    }

    # Intentionally omit household_name or any PII/medical records from AI context
    safe_family_context = {
        "configured_city": profile.city,
        "location_label": profile.location_label,
        "household_size": profile.household_size,
        "children_count": profile.children_count,
        "elderly_count": profile.elderly_count,
        "has_respiratory_sensitivity": profile.has_respiratory_condition,
        "respiratory_sensitivity_context": profile.respiratory_vulnerability or "None specified",
        "sensitivity_tier": profile.sensitivity_level.value,
        "daily_commute_method": profile.commute_method.value,
        "daily_outdoor_commute": profile.daily_outdoor_commute,
        "typical_outdoor_schedule": profile.outdoor_activity_schedule or "Not specified",
        "home_ventilation_preference": profile.ventilation_preference.value,
        "air_purifier_available": profile.has_air_purifier,
        "routine_notes": profile.notes or "None",
    }

    history_payload = [
        {"role": turn.role, "content": turn.content}
        for turn in (conversation_history or [])[-6:]
    ]

    return {
        "location": {
            "name": air_quality.location.name,
            "region": air_quality.location.region,
            "country": air_quality.location.country,
            "latitude": air_quality.location.latitude,
            "longitude": air_quality.location.longitude,
            "timezone": air_quality.location.timezone,
        },
        "telemetry_integrity": {
            "air_quality_available": assessment.air_quality_available,
            "data_status": air_quality.data_status.value,
            "is_stale": assessment.is_stale,
            "stale_reason": assessment.stale_reason,
            "api_warning": air_quality.api_warning,
            "source": air_quality.source,
            "observation_time": air_quality.observation_time,
            "fetched_at": air_quality.fetched_at.isoformat() if air_quality.fetched_at else None,
            "cached_at": air_quality.cached_at.isoformat() if air_quality.cached_at else None,
            "data_timestamp_used": assessment.data_timestamp,
        },
        "data_classification": {
            "observed_ground_sensor_data": {
                "available": observed_available,
                "note": (
                    "Direct ground station observations available."
                    if observed_available
                    else "Not available: Open-Meteo provides CAMS atmospheric model estimates, not direct ground station observations."
                ),
            },
            "model_estimated_data": {
                "available": assessment.air_quality_available,
                "pollutants": estimated_pollutants,
            },
            "forecast_data": {
                "available": len(forecast_points) > 0,
                "upcoming_hours": forecast_points,
                "summary": assessment.forecast_summary,
            },
            "missing_data": {
                "items": assessment.missing_data_items,
                "missing_pollutants": missing_pollutants,
                "instruction": (
                    "AIR QUALITY DATA IS UNAVAILABLE. You MUST state clearly that live readings are unavailable "
                    "and MUST NOT invent, guess, or fabricate any AQI or pollutant numbers."
                    if not assessment.air_quality_available
                    else "Do NOT invent any missing pollutant values or missing AQI scales."
                ),
            },
        },
        "aqi_standards": aqi_standards,
        "deterministic_decision_engine": {
            "risk_level": assessment.risk_level.value,
            "is_sensitive_household": assessment.is_sensitive_household,
            "vulnerability_reasons": assessment.vulnerability_reasons,
            "ventilation_posture": assessment.ventilation_posture,
            "outdoor_play_posture": assessment.outdoor_play_posture,
            "mask_recommended": assessment.mask_recommended,
            "high_exposure_activities": assessment.high_exposure_activities,
            "mandatory_limitations": assessment.limitations,
            "safety_rules": assessment.safety_rules_summary,
        },
        "family_profile": safe_family_context,
        "request": {
            "mode": "chat" if question else "recommendations",
            "focus_area": focus_area,
            "user_question": question or f"Provide structured {focus_area.replace('_', ' ')} air-quality recommendations for this household.",
            "recent_conversation": history_payload,
        },
    }
