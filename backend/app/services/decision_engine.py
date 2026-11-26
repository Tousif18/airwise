"""Deterministic decision engine for Urban Air Quality household safety rules.

Evaluates US AQI, European AQI (EAQI), and Indian CPCB AQI independently without
mixing scales or fabricating missing CPCB values. Keeps safety-critical decisions
independent of Gemini and generates deterministic rule-based fallback responses.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

from app.core.config import Settings
from app.schemas.air_quality import (
    AirQualityOverviewResponse,
    DataStatus,
    HourlyTrendPoint,
    PollutantReading,
    ValueKind,
)
from app.schemas.assistant import (
    AQIScaleReading,
    AssistantStructuredResponse,
    CurrentConditionsSummary,
    PollutantSnapshot,
    PriorityLevel,
    RecommendationItem,
    ResponseSourceMode,
    RiskLevel,
)
from app.schemas.family import CommuteMethod, FamilyProfile, SensitivityLevel, VentilationPreference

_RISK_ORDER: dict[RiskLevel, int] = {
    RiskLevel.UNKNOWN: 0,
    RiskLevel.LOW: 1,
    RiskLevel.MODERATE: 2,
    RiskLevel.SENSITIVE_CAUTION: 3,
    RiskLevel.HIGH: 4,
    RiskLevel.VERY_HIGH: 5,
    RiskLevel.HAZARDOUS: 6,
}


def _max_risk(levels: Iterable[RiskLevel]) -> RiskLevel:
    return max(levels, key=lambda lvl: _RISK_ORDER[lvl], default=RiskLevel.UNKNOWN)


def classify_european_aqi(eaqi: float | None) -> str:
    """Map Open-Meteo European AQI (EAQI) numeric value to official EEA bands."""
    if eaqi is None:
        return "Unavailable"
    if eaqi <= 20:
        return "Good"
    if eaqi <= 40:
        return "Fair"
    if eaqi <= 60:
        return "Moderate"
    if eaqi <= 80:
        return "Poor"
    if eaqi <= 100:
        return "Very Poor"
    return "Extremely Poor"


def _risk_from_us_aqi(us_aqi: float | None) -> RiskLevel:
    if us_aqi is None:
        return RiskLevel.UNKNOWN
    if us_aqi <= 50:
        return RiskLevel.LOW
    if us_aqi <= 100:
        return RiskLevel.MODERATE
    if us_aqi <= 150:
        return RiskLevel.SENSITIVE_CAUTION
    if us_aqi <= 200:
        return RiskLevel.HIGH
    if us_aqi <= 300:
        return RiskLevel.VERY_HIGH
    return RiskLevel.HAZARDOUS


def _risk_from_european_aqi(eaqi: float | None) -> RiskLevel:
    if eaqi is None:
        return RiskLevel.UNKNOWN
    if eaqi <= 20:
        return RiskLevel.LOW
    if eaqi <= 40:
        return RiskLevel.MODERATE
    if eaqi <= 60:
        return RiskLevel.SENSITIVE_CAUTION
    if eaqi <= 80:
        return RiskLevel.HIGH
    if eaqi <= 100:
        return RiskLevel.VERY_HIGH
    return RiskLevel.HAZARDOUS


def _risk_from_cpcb_aqi(cpcb_aqi: int | None) -> RiskLevel:
    if cpcb_aqi is None:
        return RiskLevel.UNKNOWN
    if cpcb_aqi <= 50:
        return RiskLevel.LOW
    if cpcb_aqi <= 100:
        return RiskLevel.MODERATE
    if cpcb_aqi <= 200:
        return RiskLevel.SENSITIVE_CAUTION
    if cpcb_aqi <= 300:
        return RiskLevel.HIGH
    if cpcb_aqi <= 400:
        return RiskLevel.VERY_HIGH
    return RiskLevel.HAZARDOUS


def _risk_from_pollutants(pollutants: list[PollutantReading]) -> RiskLevel:
    """Assess acute pollutant elevation against WHO/urban thresholds."""
    by_key = {p.key: p.value for p in pollutants if p.value is not None}
    risks: list[RiskLevel] = []

    pm25 = by_key.get("pm2_5")
    if pm25 is not None:
        if pm25 > 120:
            risks.append(RiskLevel.VERY_HIGH)
        elif pm25 > 60:
            risks.append(RiskLevel.HIGH)
        elif pm25 > 35:
            risks.append(RiskLevel.SENSITIVE_CAUTION)
        elif pm25 > 15:
            risks.append(RiskLevel.MODERATE)
        else:
            risks.append(RiskLevel.LOW)

    pm10 = by_key.get("pm10")
    if pm10 is not None:
        if pm10 > 250:
            risks.append(RiskLevel.HIGH)
        elif pm10 > 100:
            risks.append(RiskLevel.SENSITIVE_CAUTION)
        elif pm10 > 45:
            risks.append(RiskLevel.MODERATE)

    no2 = by_key.get("nitrogen_dioxide")
    if no2 is not None:
        if no2 > 180:
            risks.append(RiskLevel.HIGH)
        elif no2 > 80:
            risks.append(RiskLevel.SENSITIVE_CAUTION)
        elif no2 > 25:
            risks.append(RiskLevel.MODERATE)

    o3 = by_key.get("ozone")
    if o3 is not None and o3 > 100:
        risks.append(RiskLevel.SENSITIVE_CAUTION)

    return _max_risk(risks)


def _check_observation_staleness(
    air_quality: AirQualityOverviewResponse,
    settings: Settings,
) -> tuple[bool, str | None]:
    """Detect staleness from cache metadata or aged observation_time."""
    if air_quality.is_stale:
        return True, air_quality.stale_reason or "Cached telemetry exceeded freshness threshold."

    if air_quality.fetched_at is not None:
        fetched = air_quality.fetched_at
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        age_seconds = (datetime.now(timezone.utc) - fetched).total_seconds()
        if age_seconds > settings.air_quality_stale_warning_seconds and air_quality.data_status == DataStatus.CACHED:
            return True, f"Cached telemetry is {int(age_seconds // 60)} minutes old."

    if air_quality.observation_time and air_quality.data_status != DataStatus.UNAVAILABLE:
        try:
            obs_str = air_quality.observation_time.replace("Z", "+00:00")
            obs_dt = datetime.fromisoformat(obs_str)
            if obs_dt.tzinfo is None:
                # Open-Meteo local timestamps lack offset; compare conservatively only if > 24h off UTC
                obs_utc = obs_dt.replace(tzinfo=timezone.utc)
                diff_minutes = (datetime.now(timezone.utc) - obs_utc).total_seconds() / 60.0
                if diff_minutes > max(1440, settings.air_quality_observation_stale_minutes):
                    return True, (
                        f"Observation timestamp ({air_quality.observation_time}) appears outdated."
                    )
            else:
                diff_minutes = (datetime.now(timezone.utc) - obs_dt.astimezone(timezone.utc)).total_seconds() / 60.0
                if diff_minutes > settings.air_quality_observation_stale_minutes:
                    return True, (
                        f"Environmental reading is {int(diff_minutes)} minutes old "
                        f"(threshold: {settings.air_quality_observation_stale_minutes} min)."
                    )
        except ValueError:
            pass

    return False, None


def _summarize_forecast_window(hourly_trend: list[HourlyTrendPoint]) -> dict[str, str | float | None]:
    """Extract safer forecast window info without inventing missing points."""
    forecast_points = [
        pt for pt in hourly_trend
        if pt.value_kind == ValueKind.FORECAST and (pt.us_aqi is not None or pt.pm2_5 is not None)
    ]
    if not forecast_points:
        return {"available": "false", "best_time": None, "best_us_aqi": None, "peak_us_aqi": None}

    with_aqi = [pt for pt in forecast_points if pt.us_aqi is not None]
    if with_aqi:
        best = min(with_aqi, key=lambda p: p.us_aqi or 9999)
        peak = max(with_aqi, key=lambda p: p.us_aqi or -1)
        return {
            "available": "true",
            "best_time": best.time,
            "best_us_aqi": best.us_aqi,
            "peak_us_aqi": peak.us_aqi,
        }

    best_pm = min(forecast_points, key=lambda p: p.pm2_5 or 9999)
    return {
        "available": "true",
        "best_time": best_pm.time,
        "best_us_aqi": None,
        "peak_us_aqi": None,
    }


@dataclass
class DecisionAssessment:
    """Deterministic safety & guidance posture derived from AQI + family rules."""

    risk_level: RiskLevel
    air_quality_available: bool
    is_stale: bool
    stale_reason: str | None
    is_sensitive_household: bool
    vulnerability_reasons: list[str]
    high_exposure_activities: list[str]
    ventilation_posture: str  # "open_recommended", "brief_cautious", "keep_closed"
    outdoor_play_posture: str  # "safe", "limit_intense", "avoid_prolonged", "stay_indoors", "exercise_caution_unknown"
    mask_recommended: bool
    missing_data_items: list[str]
    limitations: list[str]
    forecast_summary: dict[str, str | float | None]
    current_conditions: CurrentConditionsSummary
    data_timestamp: str
    safety_rules_summary: list[str] = field(default_factory=list)


class DeterministicDecisionEngine:
    """Evaluates air quality and household vulnerability with zero LLM dependency."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def assess(
        self,
        air_quality: AirQualityOverviewResponse,
        profile: FamilyProfile,
    ) -> DecisionAssessment:
        """Produce deterministic safety assessment and structured conditions."""
        is_available = air_quality.data_status != DataStatus.UNAVAILABLE and (
            air_quality.us_aqi is not None
            or air_quality.european_aqi is not None
            or air_quality.indian_aqi.aqi is not None
            or any(p.value is not None for p in air_quality.pollutants)
        )

        is_stale, stale_reason = _check_observation_staleness(air_quality, self._settings)

        us_risk = _risk_from_us_aqi(air_quality.us_aqi)
        eaqi_risk = _risk_from_european_aqi(air_quality.european_aqi)
        cpcb_risk = _risk_from_cpcb_aqi(air_quality.indian_aqi.aqi)
        pollutant_risk = _risk_from_pollutants(air_quality.pollutants)

        base_risk = _max_risk([us_risk, eaqi_risk, cpcb_risk, pollutant_risk])
        if not is_available:
            base_risk = RiskLevel.UNKNOWN

        vulnerability_reasons: list[str] = []
        if profile.children_count > 0:
            vulnerability_reasons.append(f"{profile.children_count} child(ren) in household")
        if profile.elderly_count > 0:
            vulnerability_reasons.append(f"{profile.elderly_count} older adult(s) in household")
        if profile.has_respiratory_condition:
            vulnerability_reasons.append("respiratory sensitivity flagged")
        if profile.respiratory_vulnerability:
            vulnerability_reasons.append(f"sensitivity context: {profile.respiratory_vulnerability}")
        if profile.sensitivity_level == SensitivityLevel.HIGH:
            vulnerability_reasons.append("high household sensitivity tier")

        is_sensitive = bool(vulnerability_reasons) or profile.sensitivity_level in (
            SensitivityLevel.MODERATE,
            SensitivityLevel.HIGH,
        )

        # Escalate moderate readings to sensitive_caution for high-sensitivity households
        effective_risk = base_risk
        if (
            is_available
            and base_risk == RiskLevel.MODERATE
            and (
                profile.sensitivity_level == SensitivityLevel.HIGH
                or profile.has_respiratory_condition
                or profile.children_count > 0
                or profile.elderly_count > 0
            )
        ):
            effective_risk = RiskLevel.SENSITIVE_CAUTION

        # Ventilation & outdoor postures
        if not is_available:
            ventilation_posture = "brief_cautious"
            outdoor_play_posture = "exercise_caution_unknown"
            mask_recommended = False
        elif effective_risk == RiskLevel.LOW:
            ventilation_posture = "open_recommended"
            outdoor_play_posture = "safe"
            mask_recommended = False
        elif effective_risk == RiskLevel.MODERATE:
            ventilation_posture = "open_recommended"
            outdoor_play_posture = "safe"
            mask_recommended = False
        elif effective_risk == RiskLevel.SENSITIVE_CAUTION:
            ventilation_posture = "brief_cautious"
            outdoor_play_posture = "limit_intense"
            mask_recommended = profile.has_respiratory_condition or profile.sensitivity_level == SensitivityLevel.HIGH
        elif effective_risk == RiskLevel.HIGH:
            ventilation_posture = "keep_closed"
            outdoor_play_posture = "avoid_prolonged"
            mask_recommended = True
        else:  # VERY_HIGH or HAZARDOUS
            ventilation_posture = "keep_closed"
            outdoor_play_posture = "stay_indoors"
            mask_recommended = True

        # Identify potentially high-exposure activities
        high_exposure: list[str] = []
        if effective_risk in (
            RiskLevel.SENSITIVE_CAUTION,
            RiskLevel.HIGH,
            RiskLevel.VERY_HIGH,
            RiskLevel.HAZARDOUS,
        ):
            if profile.children_count > 0:
                high_exposure.append(
                    "Prolonged or vigorous outdoor play for children during elevated particulate/smog levels"
                )
            if profile.daily_outdoor_commute and profile.commute_method in (
                CommuteMethod.WALKING,
                CommuteMethod.CYCLING,
                CommuteMethod.TWO_WHEELER,
            ):
                high_exposure.append(
                    f"Unprotected {profile.commute_method.value.replace('_', ' ')} commute along busy traffic corridors"
                )
            elif profile.daily_outdoor_commute:
                high_exposure.append("Peak-hour traffic commute exposure near major roadways")
            if profile.ventilation_preference == VentilationPreference.NATURAL_CROSS_VENTILATION:
                high_exposure.append(
                    "Leaving windows wide open for natural cross-ventilation while outdoor pollution is elevated"
                )
            if not profile.has_air_purifier:
                high_exposure.append(
                    "Indoor cooking smoke, incense, or unventilated particulates accumulating without mechanical filtration"
                )
        elif not is_available:
            high_exposure.append(
                "Unverified outdoor exertion while live air-quality telemetry is unavailable"
            )

        # Missing data & limitations audit
        missing_data_items: list[str] = []
        limitations: list[str] = []

        if not is_available:
            missing_data_items.append("All live/cached air-quality readings are currently unavailable")
            limitations.append(
                air_quality.error_detail
                or "Open-Meteo air quality telemetry could not be retrieved; no readings were fabricated."
            )
        else:
            limitations.append(
                "Current and historical readings come from Open-Meteo CAMS atmospheric model estimates rather than direct street-level ground monitors."
            )

        if air_quality.us_aqi is None:
            missing_data_items.append("US AQI (EPA scale)")
        if air_quality.european_aqi is None:
            missing_data_items.append("European AQI (EAQI)")
        if air_quality.indian_aqi.aqi is None:
            reason = (
                air_quality.indian_aqi.unavailable_reason
                or "Required 24h/8h pollutant inputs missing for CPCB NAQI."
            )
            missing_data_items.append("Indian CPCB AQI (NAQI)")
            limitations.append(reason)

        missing_pollutants = [p.formula for p in air_quality.pollutants if p.value is None]
        if missing_pollutants:
            missing_data_items.append("Missing pollutants: " + ", ".join(missing_pollutants))

        if is_stale:
            limitations.append(
                f"Stale environmental data warning: {stale_reason}"
            )
        if air_quality.api_warning and air_quality.api_warning not in " ".join(limitations):
            limitations.append(air_quality.api_warning)

        forecast_summary = _summarize_forecast_window(air_quality.hourly_trend)

        us_scale = AQIScaleReading(
            standard_name="US AQI (EPA Scale)",
            value=air_quality.us_aqi,
            category=air_quality.aqi_category,
            status=air_quality.data_status if air_quality.us_aqi is not None else DataStatus.UNAVAILABLE,
            value_kind=air_quality.telemetry_kind if air_quality.us_aqi is not None else None,
            unavailable_reason=None if air_quality.us_aqi is not None else "US AQI reading unavailable.",
        )
        eaqi_scale = AQIScaleReading(
            standard_name="European AQI (EAQI)",
            value=air_quality.european_aqi,
            category=classify_european_aqi(air_quality.european_aqi),
            status=air_quality.data_status if air_quality.european_aqi is not None else DataStatus.UNAVAILABLE,
            value_kind=air_quality.telemetry_kind if air_quality.european_aqi is not None else None,
            unavailable_reason=None if air_quality.european_aqi is not None else "European AQI reading unavailable.",
        )
        cpcb_scale = AQIScaleReading(
            standard_name="Indian CPCB AQI (NAQI)",
            value=air_quality.indian_aqi.aqi,
            category=air_quality.indian_aqi.category,
            status=air_quality.indian_aqi.status,
            value_kind=air_quality.indian_aqi.value_kind if air_quality.indian_aqi.aqi is not None else None,
            prominent_pollutant=air_quality.indian_aqi.prominent_pollutant,
            unavailable_reason=air_quality.indian_aqi.unavailable_reason,
        )

        key_pollutants = [
            PollutantSnapshot(
                key=p.key,
                formula=p.formula,
                value=p.value,
                unit=p.unit,
                guideline_24h=p.guideline_24h,
                status=p.status,
                value_kind=p.value_kind,
                cpcb_sub_index=p.cpcb_sub_index,
                cpcb_category=p.cpcb_category,
            )
            for p in air_quality.pollutants
        ]

        current_conditions = CurrentConditionsSummary(
            location_name=air_quality.location.name,
            region=air_quality.location.region,
            country=air_quality.location.country,
            data_status=air_quality.data_status,
            telemetry_kind=air_quality.telemetry_kind,
            is_stale=is_stale,
            stale_reason=stale_reason,
            risk_level=effective_risk,
            us_aqi=us_scale,
            european_aqi=eaqi_scale,
            indian_cpcb_aqi=cpcb_scale,
            key_pollutants=key_pollutants,
            source=air_quality.source,
        )

        data_timestamp = (
            air_quality.observation_time
            or (air_quality.fetched_at.isoformat() if air_quality.fetched_at else None)
            or "Unavailable"
        )

        safety_rules_summary = [
            f"Deterministic risk posture: {effective_risk.value}",
            f"Outdoor play posture: {outdoor_play_posture}",
            f"Ventilation posture: {ventilation_posture}",
            f"Well-fitted N95/KN95 mask advisory: {'recommended outdoors' if mask_recommended else 'optional/not currently required'}",
            "Never claim masks or purifiers eliminate 100% of exposure; never claim houseplants remove indoor air pollution; never diagnose or prescribe treatment.",
        ]

        return DecisionAssessment(
            risk_level=effective_risk,
            air_quality_available=is_available,
            is_stale=is_stale,
            stale_reason=stale_reason,
            is_sensitive_household=is_sensitive,
            vulnerability_reasons=vulnerability_reasons,
            high_exposure_activities=high_exposure,
            ventilation_posture=ventilation_posture,
            outdoor_play_posture=outdoor_play_posture,
            mask_recommended=mask_recommended,
            missing_data_items=missing_data_items,
            limitations=limitations,
            forecast_summary=forecast_summary,
            current_conditions=current_conditions,
            data_timestamp=data_timestamp,
            safety_rules_summary=safety_rules_summary,
        )

    def build_fallback_response(
        self,
        assessment: DecisionAssessment,
        air_quality: AirQualityOverviewResponse,
        profile: FamilyProfile,
        question: str | None = None,
        focus_area: str = "daily_plan",
        fallback_reason: str | None = None,
    ) -> AssistantStructuredResponse:
        """Generate a complete, question-aware rule-based response when Gemini is unavailable."""
        loc = air_quality.location.name
        risk = assessment.risk_level
        pm25 = next((p.value for p in air_quality.pollutants if p.key == "pm2_5"), None)
        no2 = next((p.value for p in air_quality.pollutants if p.key == "nitrogen_dioxide"), None)
        q_lower = (question or "").lower()

        # Build clear scale-separated reading snippet
        scale_parts: list[str] = []
        if air_quality.us_aqi is not None:
            scale_parts.append(f"US AQI {int(round(air_quality.us_aqi))} ({air_quality.aqi_category})")
        if air_quality.indian_aqi.aqi is not None:
            scale_parts.append(
                f"Indian CPCB AQI {air_quality.indian_aqi.aqi} ({air_quality.indian_aqi.category})"
            )
        if air_quality.european_aqi is not None:
            scale_parts.append(
                f"European AQI {int(round(air_quality.european_aqi))} ({classify_european_aqi(air_quality.european_aqi)})"
            )
        if pm25 is not None:
            scale_parts.append(f"PM2.5 {pm25} μg/m³")
        readings_text = ", ".join(scale_parts) if scale_parts else "No live readings available"

        # Question-aware summary
        if not assessment.air_quality_available:
            summary = (
                f"Rule-based guidance for {loc}: Live air-quality readings are currently unavailable, "
                "so AirWise will not estimate or invent AQI numbers. Take basic precautions for sensitive "
                "household members and retry Refresh Live or check local official monitoring stations before "
                "prolonged outdoor exertion."
            )
        elif "child" in q_lower or "play" in q_lower:
            if assessment.outdoor_play_posture == "safe":
                summary = (
                    f"Rule-based guidance for {loc} ({readings_text}): Conditions are favorable for children's "
                    "outdoor play right now, though sensitive children should still pause if irritated."
                )
            elif assessment.outdoor_play_posture == "limit_intense":
                summary = (
                    f"Rule-based guidance for {loc} ({readings_text}): Outdoor play should be kept short and low-intensity "
                    "for children today. Favor cleaner midday forecast windows and avoid busy roadways."
                )
            else:
                summary = (
                    f"Rule-based guidance for {loc} ({readings_text}): Prolonged outdoor play is not advised for children "
                    "under current air-quality conditions. Shift play indoors with filtered air."
                )
        elif "ventilate" in q_lower or "window" in q_lower or focus_area == "indoor":
            if assessment.ventilation_posture == "open_recommended":
                summary = (
                    f"Rule-based guidance for {loc} ({readings_text}): Brief cross-ventilation is suitable right now, "
                    "especially away from busy traffic corridors."
                )
            elif assessment.ventilation_posture == "brief_cautious":
                summary = (
                    f"Rule-based guidance for {loc} ({readings_text}): Keep windows mostly closed during peak smog/traffic "
                    "hours; use brief 10-15 minute ventilation only when outdoor haze dips and pair with indoor filtration."
                )
            else:
                summary = (
                    f"Rule-based guidance for {loc} ({readings_text}): Keep exterior windows and doors closed right now "
                    "to limit outdoor PM2.5 intrusion, and run indoor air cleaning if available."
                )
        elif "commut" in q_lower or "emission" in q_lower or focus_area in ("commute", "sustainability"):
            summary = (
                f"Rule-based guidance for {loc} ({readings_text}): Shifting from private fuel vehicles to enclosed metro/bus "
                "transit or carpooling reduces personal traffic-corridor exposure and cuts household tailpipe emissions."
            )
        else:
            summary = (
                f"Rule-based guidance for {loc} ({readings_text}): Household risk posture is "
                f"{risk.value.replace('_', ' ').upper()}. "
                + (
                    "Prioritize indoor air protection and shorter, well-timed outdoor trips."
                    if risk in (RiskLevel.SENSITIVE_CAUTION, RiskLevel.HIGH, RiskLevel.VERY_HIGH, RiskLevel.HAZARDOUS)
                    else "Normal routines are broadly suitable with standard traffic-corridor awareness."
                )
            )

        recommendations: list[RecommendationItem] = []

        # 1. Outdoor activity / children recommendation
        if not assessment.air_quality_available:
            recommendations.append(
                RecommendationItem(
                    title="Verify Local Air Quality Before Prolonged Outdoor Activity",
                    description=(
                        "Because live Open-Meteo readings are unavailable, avoid intense outdoor exertion for "
                        "children, older adults, or sensitive members until local conditions are confirmed."
                    ),
                    priority=PriorityLevel.HIGH,
                    reason="Missing environmental telemetry prevents safe exposure verification.",
                    expected_benefit="Prevents accidental high-pollution exposure during blind telemetry gaps.",
                )
            )
        elif assessment.outdoor_play_posture in ("avoid_prolonged", "stay_indoors"):
            recommendations.append(
                RecommendationItem(
                    title="Move Outdoor Play & Exercise Indoors Today",
                    description=(
                        f"Avoid strenuous outdoor activity in {loc}. "
                        + (
                            f"If brief outdoor time is unavoidable, check forecast hours around {assessment.forecast_summary['best_time']}."
                            if assessment.forecast_summary.get("best_time")
                            else "Keep essential outdoor trips brief and away from main roads."
                        )
                    ),
                    priority=PriorityLevel.HIGH,
                    reason=f"Current risk level is {risk.value.replace('_', ' ')} ({readings_text}).",
                    expected_benefit="Substantially lowers inhaled particulate dose for children and sensitive adults.",
                )
            )
        elif assessment.outdoor_play_posture == "limit_intense":
            recommendations.append(
                RecommendationItem(
                    title="Shorten Outdoor Play & Avoid Traffic Corridors",
                    description=(
                        "Choose lower-intensity outdoor play in parks away from busy roads and schedule around "
                        f"your family routine ({profile.outdoor_activity_schedule or 'midday cleaner hours'})."
                    ),
                    priority=PriorityLevel.MEDIUM,
                    reason="Moderate-to-sensitive pollution elevates breathing rates during vigorous exertion.",
                    expected_benefit="Allows light outdoor activity while limiting deep-lung particle deposition.",
                )
            )
        else:
            recommendations.append(
                RecommendationItem(
                    title="Normal Outdoor Routines Suitable",
                    description=(
                        f"Outdoor activities in {loc} are generally safe at current levels; stay alert for local smoke or roadside exhaust."
                    ),
                    priority=PriorityLevel.LOW,
                    reason=f"Available AQI scales indicate {risk.value.replace('_', ' ')} risk.",
                    expected_benefit="Supports healthy outdoor movement with minimal respiratory strain.",
                )
            )

        # 2. Indoor air & ventilation recommendation
        if assessment.ventilation_posture == "keep_closed":
            purifier_tip = (
                "Run your HEPA air purifier continuously on medium-to-high in the primary living/sleeping room."
                if profile.has_air_purifier
                else "Use kitchen exhaust fans when cooking, damp-mop dust instead of dry sweeping, and avoid incense or smoke indoors."
            )
            recommendations.append(
                RecommendationItem(
                    title="Keep Windows Closed & Protect Indoor Air",
                    description=f"Seal exterior drafts during elevated smog. {purifier_tip} Note that air cleaners reduce—but do not eliminate—all indoor particles.",
                    priority=PriorityLevel.HIGH,
                    reason=f"Outdoor particulate levels ({readings_text}) can rapidly infiltrate unsealed rooms.",
                    expected_benefit="Reduces indoor PM2.5 accumulation while household members are indoors.",
                )
            )
        elif assessment.ventilation_posture == "brief_cautious":
            recommendations.append(
                RecommendationItem(
                    title="Time Ventilation to Lower-Smog Midday Windows",
                    description=(
                        "Avoid opening windows during early-morning or evening inversion/traffic peaks. "
                        "Use brief cross-ventilation only when outdoor air looks clearer, and run filtration afterward if available."
                    ),
                    priority=PriorityLevel.MEDIUM,
                    reason="Controlled window timing balances fresh air exchange against outdoor PM2.5 intrusion.",
                    expected_benefit="Limits indoor CO₂ buildup without pulling peak winter smog indoors.",
                )
            )
        else:
            recommendations.append(
                RecommendationItem(
                    title="Cross-Ventilate Living Spaces",
                    description=(
                        "Open opposite windows for 15–30 minutes to refresh indoor air, ideally away from idling traffic."
                    ),
                    priority=PriorityLevel.LOW,
                    reason="Outdoor air quality is currently within lower-risk bounds or requires cautious brief exchange.",
                    expected_benefit="Clears indoor cooking fumes and CO₂ buildup naturally.",
                )
            )

        # 3. Commute & sustainable alternative recommendation
        commute_label = profile.commute_method.value.replace("_", " ")
        recommendations.append(
            RecommendationItem(
                title="Choose Low-Exposure & Low-Emission Commute Habits",
                description=(
                    (
                        f"Current commute mode is {commute_label}. During elevated smog, enclosed metro/bus transit or carpooling "
                        "reduces roadside inhalation; wear a well-fitted N95/KN95 mask outdoors when smog is high (masks reduce exposure but do not eliminate 100%)."
                    )
                    if assessment.mask_recommended
                    else (
                        f"Current commute mode is {commute_label}. Combine errands, favor metro/bus, walking/cycling on low-traffic side streets, "
                        "or carpooling to reduce local NO₂ and particulate emissions."
                    )
                ),
                priority=PriorityLevel.HIGH if assessment.mask_recommended else PriorityLevel.MEDIUM,
                reason=(
                    f"Road traffic raises roadside PM2.5 and NO₂"
                    + (f" (current NO₂: {no2} μg/m³)." if no2 is not None else ".")
                ),
                expected_benefit="Lowers both personal corridor exposure and neighborhood tailpipe emissions.",
            )
        )

        # Action lists
        indoor_actions: list[str] = []
        if profile.has_air_purifier:
            indoor_actions.append(
                "Run your air purifier in bedrooms and main living areas with doors closed; keep filters clean (reduces indoor particulates, though it does not eliminate all exposure)."
            )
        else:
            indoor_actions.append(
                "Avoid indoor smoke sources (incense, candles, tobacco, unvented cooking) and use exhaust fans while cooking."
            )
        indoor_actions.append(
            "Use damp cloths and mops for cleaning so settled particulate dust is not kicked back into indoor air."
        )
        if assessment.ventilation_posture == "open_recommended":
            indoor_actions.append("Cross-ventilate away from main roads during cleaner daytime hours.")
        else:
            indoor_actions.append(
                "Keep exterior windows closed during peak morning/evening smog and seal large door/window gaps."
            )

        outdoor_actions: list[str] = []
        if assessment.outdoor_play_posture in ("avoid_prolonged", "stay_indoors"):
            outdoor_actions.append(
                "Postpone vigorous outdoor sports and children's playground sessions until readings improve."
            )
        elif assessment.outdoor_play_posture == "limit_intense":
            outdoor_actions.append(
                "Keep outdoor sessions brief and moderate-paced; avoid busy intersections and construction dust."
            )
        else:
            outdoor_actions.append("Outdoor walks and play are suitable; prefer green corridors away from heavy traffic.")

        if assessment.mask_recommended:
            outdoor_actions.append(
                "Wear a snug, well-fitted N95/KN95/FFP2 mask for unavoidable outdoor commutes (note: masks reduce particle inhalation when fitted properly, but do not guarantee zero exposure)."
            )
        if assessment.forecast_summary.get("best_time"):
            outdoor_actions.append(
                f"Forecast check: lowest upcoming modeled AQI window appears around {assessment.forecast_summary['best_time']}."
            )

        sustainable_alternatives = [
            "Prefer metro, bus, or carpooling over single-occupant car or idling two-wheeler trips to cut urban PM2.5 and NO₂.",
            "Bundle errands into a single trip and switch off vehicle engines at long red lights.",
            "Avoid burning dry leaves, household waste, or biomass; report local open burning where municipal channels exist.",
        ]

        reasoning_parts = [
            f"Evaluated {loc} telemetry ({air_quality.data_status.value}, {air_quality.telemetry_kind.value}) independently across available scales without mixing US AQI, European AQI, and Indian CPCB AQI.",
            f"Household context: {profile.household_size} member(s), {profile.children_count} child(ren), {profile.elderly_count} older adult(s), sensitivity '{profile.sensitivity_level.value}', commute '{commute_label}', air purifier={'yes' if profile.has_air_purifier else 'no'}.",
        ]
        if assessment.high_exposure_activities:
            reasoning_parts.append(
                "Identified higher-exposure routines: " + "; ".join(assessment.high_exposure_activities) + "."
            )
        if assessment.is_stale:
            reasoning_parts.append(f"Staleness flagged: {assessment.stale_reason}")
        if not assessment.air_quality_available:
            reasoning_parts.append("No environmental readings were invented during telemetry unavailability.")

        return AssistantStructuredResponse(
            summary=summary,
            current_conditions=assessment.current_conditions,
            recommendations=recommendations,
            indoor_actions=indoor_actions,
            outdoor_actions=outdoor_actions,
            sustainable_alternatives=sustainable_alternatives,
            reasoning=" ".join(reasoning_parts),
            estimated_environmental_impact=(
                "Replacing 2 short urban car/two-wheeler trips per week with metro, bus, carpooling, or walking on clean days "
                "helps reduce neighborhood tailpipe NO₂ and fine particulate emissions, especially during stagnant winter air."
            ),
            limitations=assessment.limitations,
            data_timestamp=assessment.data_timestamp,
            response_source=ResponseSourceMode.RULE_BASED_FALLBACK,
            is_ai_generated=False,
            model_used=None,
            fallback_reason=fallback_reason,
        )
