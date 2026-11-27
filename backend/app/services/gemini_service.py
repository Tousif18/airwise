"""Google Gemini AI Assistant service with strict validation and deterministic fallback."""

import asyncio
import json
import logging
import re
from typing import Any, Callable, TypeVar

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.core.config import Settings
from app.schemas.air_quality import AirQualityOverviewResponse
from app.schemas.assistant import (
    AssistantHealthResponse,
    AssistantStructuredResponse,
    ChatTurn,
    GeminiGeneratedGuidance,
    ResponseSourceMode,
)
from app.schemas.family import FamilyProfile
from app.services.context_builder import build_ai_context
from app.services.decision_engine import DecisionAssessment, DeterministicDecisionEngine

logger = logging.getLogger(__name__)

SchemaT = TypeVar("SchemaT", bound=BaseModel)

SYSTEM_INSTRUCTION = """You are AirWise, a practical urban air-quality assistant for families.

Follow these strict rules:
1. Ground every statement ONLY in the provided JSON context. Never invent AQI readings, pollutant concentrations, timestamps, indoor sensor readings, or city measurements.
2. If telemetry_integrity.air_quality_available is false, explicitly explain that air quality readings are unavailable and do NOT fabricate numbers.
3. Never mix or convert between US AQI (EPA scale), European AQI (EAQI), and Indian CPCB AQI (NAQI). Always label each scale clearly when citing it. If Indian CPCB AQI is unavailable, never estimate or invent it.
4. Clearly respect the difference between observed ground sensor data, CAMS atmospheric model estimates, forecast data, and user-provided household/home inputs. Mention uncertainty, stale data warnings, and missing inputs in limitations.
5. Follow the safety posture in deterministic_decision_engine (risk_level, outdoor_play_posture, ventilation_posture, mask_recommended). Never override protective limits.
6. Address the user's question directly and concisely, tailored to their family_profile (children, elderly, respiratory sensitivity, commute method, outdoor schedule, ventilation preference, air purifier availability).
7. Always explain WHY recommendations are suggested in the reasoning field and each recommendation's reason field.
8. Safety prohibitions:
   - Never diagnose diseases or prescribe medical treatments or medication dosages.
   - Never claim houseplants meaningfully remove indoor air pollution.
   - Never guarantee that masks or air purifiers eliminate all exposure or offer 100% protection.
9. Return valid JSON matching the requested schema."""

_UNSAFE_CLAIM_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"(?<!not\s)(?<!never\s)(?<!cannot\s)(?<!can't\s)(?<!won't\s)(?<!t\s)\b(eliminates?|removes?)\s+(all|100%)\s+(exposure|particles|pollution|risk)\b",
            re.I,
        ),
        "Prohibited absolute-protection claim for masks/purifiers",
    ),
    (
        re.compile(
            r"(?<!not\s)(?<!never\s)(?<!no\s)\b100%\s+(protection|safe|filtered|eliminated)\b",
            re.I,
        ),
        "Prohibited 100% protection guarantee",
    ),
    (
        re.compile(
            r"(?<!not\s)(?<!don't\s)(?<!do not\s)\b(house)?plants?\s+(can\s+)?(effectively\s+)?(remove|purify|clean|eliminate)\s+(indoor\s+)?(air\s+)?(pollution|pm2\.5|toxins|smog)\b",
            re.I,
        ),
        "Prohibited unsupported claim about plants removing indoor pollution",
    ),
    (
        re.compile(
            r"\b(you\s+have\s+(asthma|copd|bronchitis|pneumonia|an?\s+respiratory\s+disease|lung\s+disease|an\s+infection)|diagnosed\s+with|prescribe|take\s+\d+\s*mg|inhaler\s+dosage)\b",
            re.I,
        ),
        "Prohibited medical diagnosis or prescription",
    ),
]


class UnsafeAIResponseError(ValueError):
    """Raised when Gemini output violates AirWise safety or grounding rules."""


def sanitize_error_message(message: str, api_key: str | None = None) -> str:
    """Strip any secret token substrings from diagnostic error messages."""
    cleaned = message.strip()
    if api_key and api_key.strip():
        cleaned = cleaned.replace(api_key.strip(), "[REDACTED]")
    return re.sub(r"AIza[0-9A-Za-z_\-]{10,}", "[REDACTED]", cleaned)


def validate_text_safety(text_blobs: list[str]) -> None:
    """Validate text strings against AirWise medical and air-cleaning safety rules."""
    combined = "\n".join(text_blobs)
    for pattern, reason in _UNSAFE_CLAIM_PATTERNS:
        if pattern.search(combined):
            raise UnsafeAIResponseError(reason)


def validate_gemini_guidance(guidance: GeminiGeneratedGuidance) -> GeminiGeneratedGuidance:
    """Validate structured Gemini output against AirWise safety guardrails."""
    text_blobs = [
        guidance.summary,
        guidance.reasoning,
        guidance.estimated_environmental_impact,
        *guidance.indoor_actions,
        *guidance.outdoor_actions,
        *guidance.sustainable_alternatives,
        *[
            f"{rec.title} {rec.description} {rec.reason} {rec.expected_benefit}"
            for rec in guidance.recommendations
        ],
    ]
    validate_text_safety(text_blobs)
    return guidance


def _is_transient_api_error(exc: Exception) -> bool:
    """Return True for transient upstream overload/timeout errors eligible for fallback model."""
    if isinstance(exc, asyncio.TimeoutError):
        return True
    if isinstance(exc, genai_errors.ServerError):
        return True
    if isinstance(exc, genai_errors.APIError) and getattr(exc, "code", None) in (429, 500, 502, 503, 504):
        return True
    return False


class GeminiAssistantService:
    """Modular Gemini integration backed by deterministic safety rules and fallback."""

    def __init__(
        self,
        settings: Settings,
        decision_engine: DeterministicDecisionEngine | None = None,
        client_factory: Callable[[str, float], Any] | None = None,
    ) -> None:
        self._settings = settings
        self._decision_engine = decision_engine or DeterministicDecisionEngine(settings)
        self._client_factory = client_factory

    def _create_client(self) -> Any:
        if not self._settings.gemini_configured:
            return None
        api_key = (self._settings.gemini_api_key or "").strip()
        if self._client_factory is not None:
            return self._client_factory(api_key, self._settings.gemini_timeout_seconds)
        timeout_ms = max(1000, int(self._settings.gemini_timeout_seconds * 1000))
        return genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=timeout_ms),
        )

    def get_health(self) -> AssistantHealthResponse:
        """Return assistant readiness without exposing credentials."""
        configured = self._settings.gemini_configured
        return AssistantHealthResponse(
            status="ok",
            gemini_configured=configured,
            gemini_available=configured,
            gemini_model=self._settings.gemini_model,
            fallback_mode_available=True,
            message=(
                f"Gemini ({self._settings.gemini_model}) is configured with deterministic safety validation and rule-based fallback."
                if configured
                else "GEMINI_API_KEY is not configured; AirWise AI Assistant is operating in deterministic rule-based fallback mode."
            ),
        )

    def get_status(self) -> dict[str, str | bool]:
        """Backward-compatible status summary for /api/v1/assistant/status."""
        health = self.get_health()
        return {
            "configured": health.gemini_configured,
            "model": health.gemini_model,
            "status": "ready" if health.gemini_configured else "fallback_only",
            "message": health.message,
        }

    async def invoke_structured_json(
        self,
        *,
        prompt: str,
        system_instruction: str,
        schema_cls: type[SchemaT],
    ) -> tuple[SchemaT, str]:
        """Invoke Gemini with structured JSON schema and transient model fallback.

        Returns `(validated_model, actual_model_used)`.
        """
        client = self._create_client()
        if client is None:
            raise RuntimeError("GEMINI_API_KEY is not configured.")

        candidate_models = [self._settings.gemini_model, *self._settings.gemini_fallback_models]
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2,
            response_mime_type="application/json",
            response_json_schema=schema_cls.model_json_schema(),
        )

        last_exc: Exception | None = None
        for idx, model_name in enumerate(candidate_models):
            try:
                async def _call(selected_model: str = model_name) -> Any:
                    return await client.aio.models.generate_content(
                        model=selected_model,
                        contents=prompt,
                        config=config,
                    )

                response = await asyncio.wait_for(
                    _call(),
                    timeout=self._settings.gemini_timeout_seconds,
                )

                parsed = getattr(response, "parsed", None)
                if isinstance(parsed, schema_cls):
                    return parsed, model_name
                if isinstance(parsed, dict):
                    return schema_cls.model_validate(parsed), model_name

                raw_text = getattr(response, "text", None)
                if not raw_text or not isinstance(raw_text, str):
                    raise ValueError("Gemini returned an empty response payload.")
                return schema_cls.model_validate_json(raw_text), model_name
            except Exception as exc:
                last_exc = exc
                api_key = self._settings.gemini_api_key
                err_code = getattr(exc, "code", None)
                err_status = getattr(exc, "status", None)
                err_msg = sanitize_error_message(
                    str(getattr(exc, "message", None) or exc),
                    api_key=api_key,
                )
                logger.warning(
                    "Gemini call failed (model=%s, type=%s, code=%s, status=%s, detail=%s)",
                    model_name,
                    type(exc).__name__,
                    err_code,
                    err_status,
                    err_msg,
                )
                has_more = idx < len(candidate_models) - 1
                if has_more and _is_transient_api_error(exc):
                    continue
                raise

        assert last_exc is not None
        raise last_exc

    async def _invoke_gemini(self, context: dict[str, Any]) -> tuple[GeminiGeneratedGuidance, str]:
        """Call Google Gemini async API with structured JSON schema and safety validation."""
        prompt = (
            "Analyze the following verified AirWise environmental and household JSON context "
            "and respond to the user request strictly according to the system instructions.\n\n"
            f"{json.dumps(context, ensure_ascii=False)}"
        )
        guidance, model_used = await self.invoke_structured_json(
            prompt=prompt,
            system_instruction=SYSTEM_INSTRUCTION,
            schema_cls=GeminiGeneratedGuidance,
        )
        return validate_gemini_guidance(guidance), model_used

    def _merge_with_assessment(
        self,
        guidance: GeminiGeneratedGuidance,
        assessment: DecisionAssessment,
        model_used: str,
    ) -> AssistantStructuredResponse:
        """Combine validated Gemini guidance with deterministic telemetry & limitations."""
        merged_limitations: list[str] = list(assessment.limitations)
        existing_lower = {item.lower() for item in merged_limitations}
        for item in guidance.limitations:
            cleaned = item.strip()
            if cleaned and cleaned.lower() not in existing_lower:
                merged_limitations.append(cleaned)
                existing_lower.add(cleaned.lower())

        return AssistantStructuredResponse(
            summary=guidance.summary.strip(),
            current_conditions=assessment.current_conditions,
            recommendations=guidance.recommendations,
            indoor_actions=[item.strip() for item in guidance.indoor_actions if item.strip()],
            outdoor_actions=[item.strip() for item in guidance.outdoor_actions if item.strip()],
            sustainable_alternatives=[
                item.strip() for item in guidance.sustainable_alternatives if item.strip()
            ],
            reasoning=guidance.reasoning.strip(),
            estimated_environmental_impact=guidance.estimated_environmental_impact.strip(),
            limitations=merged_limitations,
            data_timestamp=assessment.data_timestamp,
            response_source=ResponseSourceMode.GEMINI,
            is_ai_generated=True,
            model_used=model_used,
            fallback_reason=None,
        )

    def format_fallback_reason(self, exc: Exception) -> str:
        """Return a safe, user-facing fallback reason without upstream details."""
        if isinstance(exc, asyncio.TimeoutError):
            return "The AI assistant timed out; deterministic rule-based guidance was provided."
        if isinstance(exc, UnsafeAIResponseError):
            return "The AI response did not pass safety checks; deterministic rule-based guidance was provided."
        if isinstance(exc, (ValidationError, json.JSONDecodeError, ValueError)):
            return "The AI assistant returned an invalid response; deterministic rule-based guidance was provided."
        return "The AI assistant is temporarily unavailable; deterministic rule-based guidance was provided."

    async def generate_guidance(
        self,
        air_quality: AirQualityOverviewResponse,
        profile: FamilyProfile,
        question: str | None = None,
        focus_area: str = "daily_plan",
        conversation_history: list[ChatTurn] | None = None,
    ) -> AssistantStructuredResponse:
        """Build context, run deterministic engine, invoke Gemini, or fall back safely."""
        assessment = self._decision_engine.assess(
            air_quality=air_quality,
            profile=profile,
        )
        context = build_ai_context(
            air_quality=air_quality,
            profile=profile,
            assessment=assessment,
            question=question,
            focus_area=focus_area,
            conversation_history=conversation_history,
        )

        if not self._settings.gemini_configured:
            return self._decision_engine.build_fallback_response(
                assessment=assessment,
                air_quality=air_quality,
                profile=profile,
                question=question,
                focus_area=focus_area,
                fallback_reason=(
                    "Gemini API key is not configured; generated deterministic rule-based guidance."
                ),
            )

        try:
            guidance, model_used = await self._invoke_gemini(context)
            return self._merge_with_assessment(guidance, assessment, model_used=model_used)
        except Exception as exc:
            fallback_reason = self.format_fallback_reason(exc)

        return self._decision_engine.build_fallback_response(
            assessment=assessment,
            air_quality=air_quality,
            profile=profile,
            question=question,
            focus_area=focus_area,
            fallback_reason=fallback_reason,
        )


# Backward-compatible symbol alias
GeminiAssistantPlaceholder = GeminiAssistantService
