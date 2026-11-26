"""Placeholder service for Google Gemini API integration."""

from app.core.config import Settings


class GeminiAssistantPlaceholder:
    """Reports Gemini configuration readiness without exposing credentials."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def get_status(self) -> dict[str, str | bool]:
        """Return safe status metadata for the AI Assistant placeholder page."""
        return {
            "configured": self._settings.gemini_configured,
            "model": self._settings.gemini_model,
            "status": "ready_for_milestone_2" if self._settings.gemini_configured else "api_key_not_set",
            "message": (
                "Gemini API key detected via environment variables. "
                "Interactive smog guidance will be enabled in the next milestone."
                if self._settings.gemini_configured
                else "Set GEMINI_API_KEY in backend/.env to enable personalized Gemini guidance in the next milestone."
            ),
        }
