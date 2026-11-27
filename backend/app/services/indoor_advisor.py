"""Indoor Air Quality Advisor service combining outdoor telemetry, home profile, and Gemini."""

import json
from typing import Any

from app.core.config import Settings
from app.schemas.air_quality import AirQualityOverviewResponse, DataStatus
from app.schemas.assistant import (
    PriorityLevel,
    ResponseSourceMode,
    RiskLevel,
)
from app.schemas.family import FamilyProfile, SensitivityLevel
from app.schemas.indoor import (
    GeminiIndoorGuidance,
    HomeEnvironmentProfile,
    HomeType,
    IndoorAdvisorResponse,
    IndoorDataAttribution,
    IndoorRecommendationCard,
    IndoorRecommendationCategory,
    KitchenVentilationType,
    WindowVentilationType,
)
from app.services.decision_engine import (
    DecisionAssessment,
    DeterministicDecisionEngine,
    classify_european_aqi,
)
from app.services.gemini_service import GeminiAssistantService, validate_text_safety

INDOOR_SYSTEM_INSTRUCTION = """You are AirWise Indoor Air Quality Advisor.

Follow these strict rules:
1. NEVER invent indoor sensor readings (such as indoor PM2.5, CO2, VOC, or humidity numbers). Explicitly acknowledge that indoor sensor readings are unavailable and rely ONLY on the user-provided home_environment and outdoor_telemetry.
2. Never mix or convert between US AQI, European AQI, and Indian CPCB AQI. Label each scale accurately when cited, and never invent missing CPCB AQI values.
3. Follow the deterministic safety posture (ventilation_posture and risk_level).
4. Provide exactly 5 practical recommendation cards covering ALL 5 required categories:
   - pm25_reduction ("Reducing Indoor PM2.5 Exposure")
   - safe_ventilation ("Safe Ventilation Timing")
   - kitchen_smoke ("Kitchen Smoke Management")
   - dust_cleaning ("Dust Reduction & Cleaning")
   - air_purifier ("Air Purifier Placement & Filter Maintenance")
5. Tailor advice specifically to home_type (apartment vs independent_house), room_count, kitchen_ventilation, windows_ventilation, has_air_purifier, has_children, and has_older_adults.
6. Safety prohibitions:
   - Never diagnose diseases or prescribe treatments.
   - Never claim houseplants meaningfully remove indoor air pollution.
   - Never guarantee that air purifiers or sealing windows eliminate 100% of indoor exposure.
7. Return valid JSON matching the requested schema."""


def _to_family_profile(home: HomeEnvironmentProfile, location_name: str) -> FamilyProfile:
    """Map home environment sensitivity flags into FamilyProfile for deterministic assessment."""
    high_sensitivity = home.has_respiratory_sensitivity or (
        home.has_children and home.has_older_adults
    )
    sensitivity = (
        SensitivityLevel.HIGH
        if high_sensitivity
        else (
            SensitivityLevel.MODERATE
            if (home.has_children or home.has_older_adults)
            else SensitivityLevel.STANDARD
        )
    )
    return FamilyProfile(
        city=location_name,
        location_label=location_name,
        household_size=max(2 if (home.has_children or home.has_older_adults) else 1, 1),
        children_count=1 if home.has_children else 0,
        elderly_count=1 if home.has_older_adults else 0,
        has_respiratory_condition=home.has_respiratory_sensitivity,
        sensitivity_level=sensitivity,
        has_air_purifier=home.has_air_purifier,
    )


def _validate_indoor_guidance(guidance: GeminiIndoorGuidance) -> GeminiIndoorGuidance:
    blobs = [
        guidance.summary,
        guidance.ventilation_verdict,
        guidance.reasoning,
        *[
            f"{card.title} {card.description} {' '.join(card.action_steps)} {card.reason} {card.expected_benefit}"
            for card in guidance.recommendations
        ],
    ]
    validate_text_safety(blobs)
    return guidance


class IndoorAirAdvisorService:
    """Generates indoor air protection guidance backed by Gemini and deterministic rules."""

    def __init__(
        self,
        settings: Settings,
        gemini_service: GeminiAssistantService,
        decision_engine: DeterministicDecisionEngine | None = None,
    ) -> None:
        self._settings = settings
        self._gemini = gemini_service
        self._decision_engine = decision_engine or DeterministicDecisionEngine(settings)

    def _build_context(
        self,
        home: HomeEnvironmentProfile,
        air_quality: AirQualityOverviewResponse,
        assessment: DecisionAssessment,
    ) -> dict[str, Any]:
        return {
            "user_provided_home_environment": home.model_dump(mode="json"),
            "indoor_sensor_readings": {
                "available": False,
                "instruction": "No indoor air-quality sensors are present. Do NOT fabricate indoor PM2.5, CO2, or VOC measurements.",
            },
            "outdoor_telemetry": {
                "location": air_quality.location.name,
                "region": air_quality.location.region,
                "country": air_quality.location.country,
                "air_quality_available": assessment.air_quality_available,
                "data_status": air_quality.data_status.value,
                "telemetry_kind": air_quality.telemetry_kind.value,
                "is_stale": assessment.is_stale,
                "stale_reason": assessment.stale_reason,
                "observation_time": air_quality.observation_time,
                "us_aqi": {"value": air_quality.us_aqi, "category": air_quality.aqi_category},
                "european_aqi": {
                    "value": air_quality.european_aqi,
                    "category": classify_european_aqi(air_quality.european_aqi),
                },
                "indian_cpcb_aqi": {
                    "value": air_quality.indian_aqi.aqi,
                    "category": air_quality.indian_aqi.category,
                    "prominent_pollutant": air_quality.indian_aqi.prominent_pollutant,
                    "unavailable_reason": air_quality.indian_aqi.unavailable_reason,
                },
                "pollutants": [
                    {
                        "formula": p.formula,
                        "value": p.value,
                        "unit": p.unit,
                        "who_24h_guideline": p.guideline_24h,
                    }
                    for p in air_quality.pollutants
                    if p.value is not None
                ],
                "forecast_summary": assessment.forecast_summary,
            },
            "deterministic_posture": {
                "risk_level": assessment.risk_level.value,
                "ventilation_posture": assessment.ventilation_posture,
                "is_sensitive_household": assessment.is_sensitive_household,
                "mandatory_limitations": assessment.limitations,
            },
        }

    def build_fallback(
        self,
        home: HomeEnvironmentProfile,
        air_quality: AirQualityOverviewResponse,
        assessment: DecisionAssessment,
        fallback_reason: str | None = None,
    ) -> IndoorAdvisorResponse:
        """Deterministic rule-based indoor recommendations covering all 5 required domains."""
        loc = air_quality.location.name
        pm25 = next((p.value for p in air_quality.pollutants if p.key == "pm2_5"), None)
        high_outdoor_risk = assessment.risk_level in (
            RiskLevel.HIGH,
            RiskLevel.VERY_HIGH,
            RiskLevel.HAZARDOUS,
        )
        caution_risk = assessment.risk_level == RiskLevel.SENSITIVE_CAUTION
        sensitive_occupants = home.has_children or home.has_older_adults or home.has_respiratory_sensitivity

        if not assessment.air_quality_available:
            ventilation_verdict = (
                "Cautious brief ventilation only — outdoor telemetry is unavailable."
            )
        elif assessment.ventilation_posture == "keep_closed":
            ventilation_verdict = (
                "Keep exterior windows and doors closed during elevated outdoor pollution."
            )
        elif assessment.ventilation_posture == "brief_cautious":
            ventilation_verdict = (
                "Limit window opening to brief 10–15 minute midday low-traffic periods."
            )
        else:
            ventilation_verdict = (
                "Safe to cross-ventilate away from direct roadside traffic."
            )

        building_label = (
            "independent house" if home.home_type == HomeType.INDEPENDENT_HOUSE else "apartment"
        )

        # 1. Reducing indoor PM2.5 exposure
        pm25_prio = (
            PriorityLevel.HIGH
            if (high_outdoor_risk or caution_risk or not assessment.air_quality_available)
            else PriorityLevel.MEDIUM
        )
        pm25_steps = [
            (
                "Keep perimeter doors, balcony sliders, and exterior window gaps sealed with weatherstripping during morning/evening smog peaks."
                if home.home_type == HomeType.APARTMENT
                else "Check ground-floor entry doors, stairwells, and window frames for drafts and close exterior doors promptly after entry."
            ),
            "Keep shoes and dusty outer jackets near the entrance so tracked outdoor soot does not circulate across rooms.",
            "Eliminate indoor combustion sources such as incense sticks, mosquito coils, candles, and tobacco smoke.",
        ]
        pm25_card = IndoorRecommendationCard(
            category=IndoorRecommendationCategory.PM25_REDUCTION,
            category_label="Reducing Indoor PM2.5 Exposure",
            title="Seal Smog Entry Points & Cut Indoor Particle Sources",
            description=(
                f"In a {home.room_count}-room {building_label}, minimizing outdoor infiltration and avoiding indoor smoke "
                "keeps indoor PM2.5 significantly lower when outdoor air is degraded."
            ),
            action_steps=pm25_steps,
            priority=pm25_prio,
            reason=(
                f"Outdoor PM2.5 is {pm25} μg/m³ ({assessment.risk_level.value.replace('_', ' ')} risk)"
                if pm25 is not None
                else "Outdoor telemetry is unavailable or limited; minimizing infiltration protects sensitive occupants."
            ),
            expected_benefit="Reduces indoor fine-particulate accumulation across living and sleeping rooms.",
        )

        # 2. Safe ventilation based on outdoor AQI
        if not assessment.air_quality_available:
            win_detail = (
                "Outdoor conditions cannot be verified right now. Avoid routine or prolonged window opening; "
                "if ventilation is necessary, use only a brief cautious airing when there are no visible signs "
                "of smoke or nearby pollution, then close the windows."
            )
        elif home.windows_ventilation == WindowVentilationType.CROSS_VENTILATION:
            win_detail = (
                "Use short opposite-window cross-ventilation only during midday cleaner hours."
                if (high_outdoor_risk or caution_risk)
                else "Open opposite windows for 15–20 minutes to flush indoor CO₂ and humidity."
            )
        elif home.windows_ventilation == WindowVentilationType.SINGLE_SIDE_WINDOWS:
            win_detail = (
                "Single-sided windows exchange air slowly; pair brief midday opening with a circulating fan facing outward."
            )
        else:
            win_detail = (
                "Because natural window flow is limited/sealed, rely on brief doorway/exhaust air exchange during cleaner midday hours and indoor filtration."
            )
        if assessment.forecast_summary.get("best_time"):
            win_detail += f" Forecast shows a lower-AQI window around {assessment.forecast_summary['best_time']}."

        vent_card = IndoorRecommendationCard(
            category=IndoorRecommendationCategory.SAFE_VENTILATION,
            category_label="Safe Ventilation Timing",
            title=ventilation_verdict,
            description=win_detail,
            action_steps=[
                (
                    "Keep windows shut during early morning (6–9 AM) and late evening inversion/traffic peaks."
                    if (high_outdoor_risk or caution_risk or not assessment.air_quality_available)
                    else "Avoid opening windows facing heavy road traffic during rush hour."
                ),
                (
                    "Outdoor conditions are unavailable: avoid routine or prolonged window opening. If ventilation is necessary, air the room briefly only when there are no visible signs of smoke or nearby pollution, then close windows."
                    if not assessment.air_quality_available
                    else "Open windows briefly only when outdoor haze dips or during midday sunlight hours."
                ),
            ],
            priority=PriorityLevel.HIGH if high_outdoor_risk else PriorityLevel.MEDIUM,
            reason=(
                f"Outdoor risk posture is {assessment.risk_level.value.replace('_', ' ')} with {home.windows_ventilation.value.replace('_', ' ')}."
            ),
            expected_benefit="Balances indoor CO₂/moisture relief while avoiding pulling peak smog indoors.",
        )

        # 3. Kitchen smoke management
        if home.kitchen_ventilation == KitchenVentilationType.CHIMNEY_EXHAUST:
            k_prio = PriorityLevel.MEDIUM
            k_desc = "Run your kitchen chimney/range hood on medium-high 5 minutes before high-heat frying or tadka and keep it on 10 minutes afterward."
        elif home.kitchen_ventilation == KitchenVentilationType.EXHAUST_FAN:
            k_prio = PriorityLevel.HIGH if high_outdoor_risk else PriorityLevel.MEDIUM
            k_desc = "Turn on the kitchen exhaust fan throughout cooking and close the kitchen door to isolate cooking aerosols from bedrooms."
        else:
            k_prio = PriorityLevel.HIGH
            k_desc = (
                "Without a dedicated chimney or exhaust fan, cooking fumes rapidly elevate indoor PM2.5 and NO₂ across all rooms. "
                "Cover pots with lids, favor steaming/pressure-cooking over deep frying, and crack a kitchen window briefly during active cooking."
            )

        kitchen_card = IndoorRecommendationCard(
            category=IndoorRecommendationCategory.KITCHEN_SMOKE,
            category_label="Kitchen Smoke Management",
            title="Vent Cooking Fumes & Contain Ultrafine Aerosols",
            description=k_desc,
            action_steps=[
                "Keep kitchen-to-living doors closed while frying or grilling.",
                "Clean range hood grease baffles or exhaust blades monthly so airflow stays effective.",
                "Use lids on pans and lower-smoke cooking methods on severe smog days.",
            ],
            priority=k_prio,
            reason=f"User-reported kitchen ventilation: {home.kitchen_ventilation.value.replace('_', ' ')}.",
            expected_benefit="Prevents indoor PM2.5 and NO₂ spikes during meal preparation.",
        )

        # 4. Dust reduction and cleaning
        dust_card = IndoorRecommendationCard(
            category=IndoorRecommendationCategory.DUST_CLEANING,
            category_label="Dust Reduction & Cleaning",
            title="Switch to Damp Cleaning & Washable Dust Traps",
            description=(
                "Dry brooming and feather dusting resuspend settled PM10 and soot into breathing zones—especially harmful for "
                + ("children and older adults." if sensitive_occupants else "all household occupants.")
            ),
            action_steps=[
                "Damp-mop hard floors and wipe horizontal surfaces with a damp microfiber cloth.",
                "Wash bedsheets, pillow covers, and heavy curtains regularly in warm water.",
                "Use a HEPA-filtered vacuum if available rather than dry sweeping.",
            ],
            priority=PriorityLevel.HIGH if sensitive_occupants and high_outdoor_risk else PriorityLevel.MEDIUM,
            reason=(
                "Dust resuspension adds coarse and fine particulate load indoors"
                + (" with children/older adults present." if sensitive_occupants else ".")
            ),
            expected_benefit="Keeps settled particulate dust out of household breathing zones.",
        )

        # 5. Air purifier placement & filter maintenance
        if home.has_air_purifier:
            purifier_prio = PriorityLevel.HIGH if (high_outdoor_risk or sensitive_occupants) else PriorityLevel.MEDIUM
            purifier_title = "Optimize Air Purifier Placement & Filter Schedule"
            purifier_desc = (
                f"With {home.room_count} room(s) and 1+ purifier available, prioritize bedrooms overnight and the main family room during the day "
                "with doors closed. Note that air purifiers reduce—but do not eliminate—all indoor particulates."
            )
            purifier_steps = [
                "Place the purifier away from walls/curtains (at least 30–50 cm clearance) and near the center/breathing side of the occupied room.",
                "Keep room doors closed while running on medium or auto mode so clean-air delivery rate (CADR) stays effective.",
                "Vacuum the outer washable pre-filter every 2–4 weeks and replace true-HEPA filters on schedule (never wash disposable HEPA media).",
            ]
        else:
            purifier_prio = PriorityLevel.HIGH if (high_outdoor_risk and sensitive_occupants) else PriorityLevel.MEDIUM
            purifier_title = "Protect Clean-Air Sleeping Zones Without a Commercial Purifier"
            purifier_desc = (
                "Since no commercial air purifier is currently available, create a low-smoke sleeping room by sealing drafts and eliminating indoor combustion. "
                "If considering filtration, size a true-HEPA unit (or DIY MERV-13 box-fan filter) to the bedroom area—remembering no filter removes 100% of exposure."
            )
            purifier_steps = [
                "Designate bedrooms used by children or older adults as strict no-smoke, low-draft zones.",
                "If buying a HEPA purifier later, match CADR to room square footage rather than running an undersized unit across all rooms.",
                "Avoid ozone-generating 'ionizer' purifiers, which can create irritating indoor ozone.",
            ]

        purifier_card = IndoorRecommendationCard(
            category=IndoorRecommendationCategory.AIR_PURIFIER,
            category_label="Air Purifier & Filter Maintenance",
            title=purifier_title,
            description=purifier_desc,
            action_steps=purifier_steps,
            priority=purifier_prio,
            reason=f"Air purifier availability: {'yes' if home.has_air_purifier else 'no'} across {home.room_count} room(s).",
            expected_benefit="Lowers particulate concentration in highest-occupancy rooms during sleep and rest.",
        )

        summary = (
            f"Rule-based indoor air guide for your {home.room_count}-room {building_label} in {loc}: "
            f"{ventilation_verdict} Because no indoor air sensors are connected, these recommendations combine "
            f"your home setup with outdoor telemetry ({air_quality.data_status.value})."
        )

        limitations = list(assessment.limitations)
        limitations.insert(
            0,
            "No indoor air-quality sensor readings are connected; guidance uses user-provided home setup and outdoor telemetry only.",
        )

        return IndoorAdvisorResponse(
            summary=summary,
            ventilation_verdict=ventilation_verdict,
            outdoor_conditions=assessment.current_conditions,
            data_attribution=IndoorDataAttribution(
                user_provided_home_profile=home,
                outdoor_data_status=air_quality.data_status,
                outdoor_telemetry_kind=air_quality.telemetry_kind,
            ),
            recommendations=[
                pm25_card,
                vent_card,
                kitchen_card,
                dust_card,
                purifier_card,
            ],
            reasoning=(
                f"Evaluated outdoor conditions in {loc} ({air_quality.data_status.value}, "
                f"risk={assessment.risk_level.value}) alongside user-provided home parameters "
                f"({building_label}, {home.room_count} rooms, kitchen={home.kitchen_ventilation.value}, "
                f"windows={home.windows_ventilation.value}, purifier={'yes' if home.has_air_purifier else 'no'}, "
                f"children={'yes' if home.has_children else 'no'}, older_adults={'yes' if home.has_older_adults else 'no'})."
            ),
            limitations=limitations,
            data_timestamp=assessment.data_timestamp,
            response_source=ResponseSourceMode.RULE_BASED_FALLBACK,
            is_ai_generated=False,
            model_used=None,
            fallback_reason=fallback_reason,
        )

    async def generate_recommendations(
        self,
        home: HomeEnvironmentProfile,
        air_quality: AirQualityOverviewResponse,
    ) -> IndoorAdvisorResponse:
        """Generate personalized indoor air recommendations via Gemini or fallback."""
        family_proxy = _to_family_profile(home, air_quality.location.name)
        assessment = self._decision_engine.assess(
            air_quality=air_quality,
            profile=family_proxy,
        )

        if not self._settings.gemini_configured:
            return self.build_fallback(
                home=home,
                air_quality=air_quality,
                assessment=assessment,
                fallback_reason="Gemini API key is not configured; generated deterministic rule-based indoor guidance.",
            )

        context = self._build_context(home=home, air_quality=air_quality, assessment=assessment)
        prompt = (
            "Generate personalized indoor air-quality recommendations based strictly on this verified "
            "user-provided home environment and outdoor telemetry JSON context.\n\n"
            f"{json.dumps(context, ensure_ascii=False)}"
        )

        try:
            guidance, model_used = await self._gemini.invoke_structured_json(
                prompt=prompt,
                system_instruction=INDOOR_SYSTEM_INSTRUCTION,
                schema_cls=GeminiIndoorGuidance,
            )
            _validate_indoor_guidance(guidance)
        except Exception as exc:
            return self.build_fallback(
                home=home,
                air_quality=air_quality,
                assessment=assessment,
                fallback_reason=self._gemini.format_fallback_reason(exc),
            )

        merged_limitations = [
            "No indoor air-quality sensor readings are connected; guidance uses user-provided home setup and outdoor telemetry only.",
            *assessment.limitations,
        ]
        existing = {item.lower() for item in merged_limitations}
        for item in guidance.limitations:
            cleaned = item.strip()
            if cleaned and cleaned.lower() not in existing:
                merged_limitations.append(cleaned)
                existing.add(cleaned.lower())

        return IndoorAdvisorResponse(
            summary=guidance.summary.strip(),
            ventilation_verdict=guidance.ventilation_verdict.strip(),
            outdoor_conditions=assessment.current_conditions,
            data_attribution=IndoorDataAttribution(
                user_provided_home_profile=home,
                outdoor_data_status=air_quality.data_status,
                outdoor_telemetry_kind=air_quality.telemetry_kind,
            ),
            recommendations=guidance.recommendations,
            reasoning=guidance.reasoning.strip(),
            limitations=merged_limitations,
            data_timestamp=assessment.data_timestamp,
            response_source=ResponseSourceMode.GEMINI,
            is_ai_generated=True,
            model_used=model_used,
            fallback_reason=None,
        )
