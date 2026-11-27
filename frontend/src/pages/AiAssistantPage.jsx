import { useState } from "react";
import {
  Bot,
  KeyRound,
  Loader2,
  Send,
  ShieldCheck,
  Sparkles,
  Trash2,
  User,
} from "lucide-react";
import RecommendationCards from "../components/assistant/RecommendationCards";
import { ErrorBanner } from "../components/common/StateFeedback";
import FamilyProfileCard from "../components/dashboard/FamilyProfileCard";
import {
  postAssistantChat,
  postAssistantRecommendations,
} from "../services/api";

const SUGGESTED_QUESTIONS = [
  "Is it a good day for my child to play outdoors?",
  "How should my family plan today's activities?",
  "How can we improve indoor air quality?",
  "Should we ventilate our home right now?",
  "What are better commuting alternatives?",
  "How can we reduce our family's contribution to emissions?",
  "Why are these recommendations being suggested?",
];

export default function AiAssistantPage({
  assistantStatus,
  selectedLocation,
  airQuality,
  presets = [],
  familyProfile,
  familyLoading,
  familyError,
  onSaveFamilyProfile,
  onBackToDashboard,
}) {
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showProfilePanel, setShowProfilePanel] = useState(false);

  const geminiConfigured = Boolean(assistantStatus?.gemini_configured ?? assistantStatus?.configured);

  const buildLocationPayload = () => {
    if (selectedLocation?.latitude != null && selectedLocation?.longitude != null) {
      return {
        location_id: selectedLocation.id,
        latitude: selectedLocation.latitude,
        longitude: selectedLocation.longitude,
        location_name: selectedLocation.name,
        region: selectedLocation.region || "",
        country: selectedLocation.country || "",
        timezone: selectedLocation.timezone || "auto",
      };
    }
    if (selectedLocation?.id) {
      return { location_id: selectedLocation.id };
    }
    return {};
  };

  const buildHistory = (currentMessages) =>
    currentMessages.slice(-6).map((msg) => ({
      role: msg.role,
      content: msg.role === "user" ? msg.text : msg.data?.summary || msg.text || "",
    }));

  const handleAsk = async (rawText) => {
    const trimmed = rawText.trim();
    if (!trimmed || loading) return;

    setError(null);
    const userEntry = {
      id: `user-${Date.now()}`,
      role: "user",
      text: trimmed,
    };
    const nextMessages = [...messages, userEntry];
    setMessages(nextMessages);
    setQuestion("");
    setLoading(true);

    try {
      const response = await postAssistantChat({
        question: trimmed,
        ...buildLocationPayload(),
        family_profile: familyProfile || undefined,
        conversation_history: buildHistory(messages),
      });
      setMessages((prev) => [
        ...prev,
        {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          data: response,
        },
      ]);
    } catch (err) {
      setError(
        err.message || "Unable to reach the AirWise AI Assistant backend."
      );
    } finally {
      setLoading(false);
    }
  };

  const handleDailyRecommendations = async () => {
    if (loading) return;
    setError(null);
    const label = `Generate today's structured family air-quality plan for ${
      selectedLocation?.name || familyProfile?.city || "my location"
    }.`;
    setMessages((prev) => [
      ...prev,
      { id: `user-${Date.now()}`, role: "user", text: label },
    ]);
    setLoading(true);

    try {
      const response = await postAssistantRecommendations({
        focus_area: "daily_plan",
        ...buildLocationPayload(),
        family_profile: familyProfile || undefined,
      });
      setMessages((prev) => [
        ...prev,
        {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          data: response,
        },
      ]);
    } catch (err) {
      setError(
        err.message || "Unable to generate structured recommendations."
      );
    } finally {
      setLoading(false);
    }
  };

  const handleClearChat = () => {
    setMessages([]);
    setError(null);
  };

  return (
    <div className="space-y-6">
      {/* Top Assistant Status & Controls */}
      <section className="rounded-2xl border border-mist-200 bg-white p-5 shadow-xs">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-start gap-3.5">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-pine-700 text-white shadow-xs">
              <Bot className="h-5 w-5" />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="font-display text-lg font-bold text-slate-900">
                  AirWise AI Assistant
                </h2>
                <span
                  className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${
                    geminiConfigured
                      ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                      : "border-amber-200 bg-amber-50 text-amber-800"
                  }`}
                >
                  <KeyRound className="h-3 w-3" />
                  {geminiConfigured
                    ? `Gemini Ready (${assistantStatus?.gemini_model || assistantStatus?.model || "gemini-2.5-flash"})`
                    : "Rule-Based Fallback Mode"}
                </span>
              </div>
              <p className="mt-1 text-xs leading-relaxed text-slate-600">
                Grounded in {selectedLocation?.name || "selected city"} Open-Meteo telemetry (
                {airQuality?.data_status || "loading"}
                {airQuality?.us_aqi != null ? `, US AQI ${Math.round(airQuality.us_aqi)}` : ""}
                {airQuality?.indian_aqi?.aqi != null
                  ? `, CPCB ${airQuality.indian_aqi.aqi}`
                  : ""}
                ) and deterministic household safety rules.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={handleDailyRecommendations}
              disabled={loading}
              className="inline-flex items-center gap-1.5 rounded-xl bg-pine-700 px-3.5 py-2 text-xs font-semibold text-white shadow-xs transition hover:bg-pine-800 disabled:opacity-60"
            >
              <Sparkles className="h-3.5 w-3.5" />
              Get Daily Plan
            </button>

            <button
              type="button"
              onClick={() => setShowProfilePanel((prev) => !prev)}
              className="inline-flex items-center gap-1.5 rounded-xl border border-mist-200 bg-mist-50 px-3 py-2 text-xs font-semibold text-slate-700 transition hover:bg-mist-100"
            >
              {showProfilePanel ? "Hide Family Profile" : "Edit Family Profile"}
            </button>

            {messages.length > 0 && (
              <button
                type="button"
                onClick={handleClearChat}
                className="inline-flex items-center gap-1.5 rounded-xl border border-mist-200 bg-white px-3 py-2 text-xs font-semibold text-slate-600 transition hover:bg-mist-50"
              >
                <Trash2 className="h-3.5 w-3.5" />
                Clear Chat
              </button>
            )}

            {onBackToDashboard && (
              <button
                type="button"
                onClick={onBackToDashboard}
                className="rounded-xl border border-mist-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 transition hover:bg-mist-50"
              >
                Dashboard
              </button>
            )}
          </div>
        </div>
      </section>

      {/* Collapsible Family Profile Form right on the Assistant Page */}
      {showProfilePanel && (
        <FamilyProfileCard
          profile={familyProfile}
          loading={familyLoading}
          error={familyError}
          onSaveProfile={onSaveFamilyProfile}
          presets={presets}
        />
      )}

      {error && (
        <ErrorBanner
          title="Assistant request could not be completed"
          message={error}
        />
      )}

      {/* Main Conversational Workspace */}
      <section className="rounded-2xl border border-mist-200 bg-white p-5 shadow-xs">
        {messages.length === 0 ? (
          <div className="space-y-5">
            <div className="rounded-2xl border border-pine-600/15 bg-pine-50/50 p-4">
              <div className="flex items-start gap-3">
                <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-pine-700" />
                <div className="space-y-1.5 text-xs leading-relaxed text-slate-700">
                  <p className="text-sm font-bold text-slate-900">
                    Welcome to your Household Air-Quality Advisor
                  </p>
                  <p>
                    Ask about outdoor play for children, home ventilation timing, indoor air
                    cleaning, lower-exposure commutes, or why specific safety actions are
                    recommended for your household.
                  </p>
                  <p className="text-slate-600">
                    AirWise keeps US AQI, European AQI, and Indian CPCB AQI strictly separate,
                    flags stale or missing telemetry honestly, and automatically falls back to
                    deterministic rule-based guidance if Gemini is unavailable.
                  </p>
                </div>
              </div>
            </div>

            <div>
              <p className="mb-2.5 text-xs font-semibold uppercase tracking-wider text-slate-500">
                Suggested Questions
              </p>
              <div className="flex flex-wrap gap-2">
                {SUGGESTED_QUESTIONS.map((item) => (
                  <button
                    key={item}
                    type="button"
                    disabled={loading}
                    onClick={() => handleAsk(item)}
                    className="rounded-xl border border-mist-200 bg-mist-50/80 px-3 py-2 text-left text-xs font-medium text-slate-700 transition hover:border-pine-600/30 hover:bg-pine-50 hover:text-pine-900 disabled:opacity-60"
                  >
                    {item}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            {messages.map((msg) =>
              msg.role === "user" ? (
                <div key={msg.id} className="flex justify-end">
                  <div className="flex max-w-2xl items-start gap-2.5 rounded-2xl bg-pine-700 px-4 py-3 text-sm text-white shadow-xs">
                    <User className="mt-0.5 h-4 w-4 shrink-0 opacity-80" />
                    <span>{msg.text}</span>
                  </div>
                </div>
              ) : (
                <div key={msg.id} className="space-y-2">
                  <RecommendationCards data={msg.data} />
                </div>
              )
            )}

            {!loading && (
              <div className="border-t border-mist-100 pt-4">
                <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                  Follow-up questions
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {SUGGESTED_QUESTIONS.map((item) => (
                    <button
                      key={item}
                      type="button"
                      onClick={() => handleAsk(item)}
                      className="rounded-lg border border-mist-200 bg-mist-50 px-2.5 py-1 text-[11px] font-medium text-slate-700 transition hover:bg-pine-50 hover:text-pine-900"
                    >
                      {item}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {loading && (
          <div
            role="status"
            aria-live="polite"
            aria-atomic="true"
            className="mt-5 flex items-center gap-3 rounded-xl border border-mist-200 bg-mist-50 px-4 py-3 text-xs font-medium text-slate-700"
          >
            <Loader2 className="h-4 w-4 animate-spin text-pine-700" />
            <span>
              Evaluating {selectedLocation?.name || "local"} telemetry, safety rules, and
              household profile...
            </span>
          </div>
        )}

        {/* Chat Input Bar */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleAsk(question);
          }}
          className="mt-5 flex flex-col gap-2 border-t border-mist-100 pt-4 sm:flex-row"
        >
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            maxLength={1000}
            placeholder="Ask about outdoor play, window ventilation, indoor air, or commutes..."
            aria-label="Ask AirWise AI Assistant"
            className="flex-1 rounded-xl border border-mist-200 bg-mist-50/40 px-4 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-pine-600 focus:bg-white focus:outline-none"
          />
          <button
            type="submit"
            disabled={loading || !question.trim()}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-pine-700 px-5 py-2.5 text-sm font-semibold text-white shadow-xs transition hover:bg-pine-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
            <span>Ask AirWise</span>
          </button>
        </form>
      </section>
    </div>
  );
}
