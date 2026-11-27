import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  Bot,
  Building2,
  ChefHat,
  Clock,
  Fan,
  Home,
  Info,
  Loader2,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  SprayCan,
  Wind,
} from "lucide-react";
import { ErrorBanner } from "../components/common/StateFeedback";
import {
  loadLocalHomeEnvironment,
  postIndoorRecommendations,
  saveLocalHomeEnvironment,
} from "../services/api";

const CATEGORY_META = {
  pm25_reduction: {
    label: "Indoor PM2.5 Reduction",
    icon: ShieldAlert,
    accent: "bg-rose-50 text-rose-700",
  },
  safe_ventilation: {
    label: "Safe Ventilation",
    icon: Wind,
    accent: "bg-sky-50 text-sky-700",
  },
  kitchen_smoke: {
    label: "Kitchen Smoke",
    icon: ChefHat,
    accent: "bg-amber-50 text-amber-700",
  },
  dust_cleaning: {
    label: "Dust & Cleaning",
    icon: SprayCan,
    accent: "bg-emerald-50 text-emerald-700",
  },
  air_purifier: {
    label: "Air Purifier & Filters",
    icon: Fan,
    accent: "bg-pine-50 text-pine-700",
  },
};

const PRIORITY_STYLES = {
  high: { label: "High Priority", classes: "bg-rose-50 text-rose-800 border-rose-200" },
  medium: { label: "Medium Priority", classes: "bg-amber-50 text-amber-800 border-amber-200" },
  low: { label: "Low Priority", classes: "bg-emerald-50 text-emerald-800 border-emerald-200" },
};

function buildDefaultHomeEnv(familyProfile) {
  const saved = loadLocalHomeEnvironment();
  if (saved) return saved;
  return {
    home_type: "apartment",
    room_count: 3,
    kitchen_ventilation: "exhaust_fan",
    windows_ventilation: "cross_ventilation",
    has_air_purifier: Boolean(familyProfile?.has_air_purifier ?? familyProfile?.has_hepa_purifier),
    has_children: Boolean(
      (familyProfile?.children_count ?? 0) > 0 || familyProfile?.has_young_children
    ),
    has_older_adults: Boolean(
      (familyProfile?.elderly_count ?? 0) > 0 || familyProfile?.has_older_adults
    ),
    has_respiratory_sensitivity: Boolean(familyProfile?.has_respiratory_condition),
    notes: "",
  };
}

export default function IndoorAirGuidePage({
  selectedLocation,
  airQuality,
  familyProfile,
  onBackToDashboard,
}) {
  const [homeEnv, setHomeEnv] = useState(() => buildDefaultHomeEnv(familyProfile));
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const activeRequestIdRef = useRef(0);
  const selectedLocationId = selectedLocation?.id ?? null;

  useEffect(() => {
    saveLocalHomeEnvironment(homeEnv);
  }, [homeEnv]);

  useEffect(() => {
    activeRequestIdRef.current += 1;
    setResult(null);
    setError(null);
    setLoading(false);
  }, [selectedLocationId]);

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

  const handleGenerate = async (event) => {
    if (event) event.preventDefault();
    if (loading) return;

    const requestId = ++activeRequestIdRef.current;
    setError(null);
    setLoading(true);
    try {
      const data = await postIndoorRecommendations({
        home_environment: homeEnv,
        ...buildLocationPayload(),
      });
      if (requestId === activeRequestIdRef.current) {
        setResult(data);
      }
    } catch (err) {
      if (requestId === activeRequestIdRef.current) {
        setError(
          err.message || "Unable to generate indoor air-quality recommendations."
        );
      }
    } finally {
      if (requestId === activeRequestIdRef.current) {
        setLoading(false);
      }
    }
  };

  const updateHomeEnv = (updater) => {
    setHomeEnv((prev) =>
      typeof updater === "function" ? updater(prev) : updater
    );
    setResult(null);
    setError(null);
  };

  const toggleFlag = (field) => {
    updateHomeEnv((prev) => ({ ...prev, [field]: !prev[field] }));
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <section className="rounded-2xl border border-mist-200 bg-white p-5 shadow-xs">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-start gap-3.5">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-pine-700 text-white shadow-xs">
              <Home className="h-5 w-5" />
            </div>
            <div>
              <h2 className="font-display text-lg font-bold text-slate-900">
                Indoor Air Quality Advisor
              </h2>
              <p className="mt-1 text-xs leading-relaxed text-slate-600">
                Combines your user-provided home environment with current{" "}
                <span className="font-semibold text-slate-800">
                  {selectedLocation?.name || "selected city"}
                </span>{" "}
                outdoor Open-Meteo telemetry (
                {airQuality?.data_status || "loading"}
                {airQuality?.us_aqi != null
                  ? `, US AQI ${Math.round(airQuality.us_aqi)}`
                  : ""}
                {airQuality?.indian_aqi?.aqi != null
                  ? `, CPCB ${airQuality.indian_aqi.aqi}`
                  : ""}
                ) to guide safe ventilation, kitchen exhaust, dust control, and purifier use.
              </p>
            </div>
          </div>

          {onBackToDashboard && (
            <button
              type="button"
              onClick={onBackToDashboard}
              className="self-start rounded-xl border border-mist-200 bg-mist-50 px-3.5 py-2 text-xs font-semibold text-slate-700 transition hover:bg-mist-100 lg:self-auto"
            >
              Back to Dashboard
            </button>
          )}
        </div>

        {/* Data Attribution Note: Never invent indoor sensor readings */}
        <div className="mt-4 flex items-start gap-2.5 rounded-xl border border-mist-200 bg-mist-50/80 px-3.5 py-2.5 text-xs text-slate-700">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-pine-700" />
          <p>
            <span className="font-semibold text-slate-900">
              Data Distinction &amp; Medical Disclaimer:{" "}
            </span>
            AirWise does not invent indoor sensor measurements. Your home inputs below are
            <span className="font-medium"> user-provided</span>, while outdoor AQI comes from{" "}
            <span className="font-medium">
              Open-Meteo ({airQuality?.telemetry_kind || "estimated"} / {airQuality?.data_status || "checking"})
            </span>
            . Recommendations are informational only and not medical advice.
          </p>
        </div>
      </section>

      {/* Home Environment Form */}
      <section className="rounded-2xl border border-mist-200 bg-white p-5 shadow-xs">
        <div className="flex items-center gap-2 border-b border-mist-100 pb-3">
          <Building2 className="h-4 w-4 text-pine-700" />
          <h3 className="font-display text-base font-bold text-slate-900">
            1. Configure Your Home Environment (User-Provided)
          </h3>
        </div>

        <form onSubmit={handleGenerate} className="mt-4 space-y-4">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <label className="block text-xs font-medium text-slate-700">
                Home Type
              </label>
              <select
                value={homeEnv.home_type}
                onChange={(e) =>
                  updateHomeEnv((prev) => ({ ...prev, home_type: e.target.value }))
                }
                className="mt-1 w-full rounded-xl border border-mist-200 bg-white px-3 py-2 text-sm focus:border-pine-600 focus:outline-none"
              >
                <option value="apartment">Apartment / Flat</option>
                <option value="independent_house">Independent House</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700">
                Number of Rooms
              </label>
              <input
                type="number"
                min={1}
                max={20}
                value={homeEnv.room_count}
                onChange={(e) =>
                  updateHomeEnv((prev) => ({
                    ...prev,
                    room_count: Math.min(20, Math.max(1, Number(e.target.value) || 1)),
                  }))
                }
                className="mt-1 w-full rounded-xl border border-mist-200 px-3 py-2 text-sm focus:border-pine-600 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700">
                Kitchen Ventilation
              </label>
              <select
                value={homeEnv.kitchen_ventilation}
                onChange={(e) =>
                  updateHomeEnv((prev) => ({
                    ...prev,
                    kitchen_ventilation: e.target.value,
                  }))
                }
                className="mt-1 w-full rounded-xl border border-mist-200 bg-white px-3 py-2 text-sm focus:border-pine-600 focus:outline-none"
              >
                <option value="chimney_exhaust">Chimney / Ducted Range Hood</option>
                <option value="exhaust_fan">Wall Exhaust Fan</option>
                <option value="window_only">Kitchen Window Only</option>
                <option value="none">No Kitchen Exhaust / Window</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700">
                Windows &amp; Ventilation
              </label>
              <select
                value={homeEnv.windows_ventilation}
                onChange={(e) =>
                  updateHomeEnv((prev) => ({
                    ...prev,
                    windows_ventilation: e.target.value,
                  }))
                }
                className="mt-1 w-full rounded-xl border border-mist-200 bg-white px-3 py-2 text-sm focus:border-pine-600 focus:outline-none"
              >
                <option value="cross_ventilation">Cross-Ventilation (2+ sides)</option>
                <option value="single_side_windows">Single-Side Windows</option>
                <option value="limited_or_sealed">Limited / Mostly Sealed</option>
              </select>
            </div>
          </div>

          <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
            {[
              ["has_air_purifier", "Air purifier available at home"],
              ["has_children", "Children live in the home"],
              ["has_older_adults", "Older adults (60+) at home"],
              ["has_respiratory_sensitivity", "Respiratory sensitivity (non-medical flag)"],
            ].map(([field, label]) => (
              <label
                key={field}
                className="flex cursor-pointer items-center gap-2.5 rounded-xl border border-mist-200 bg-mist-50/70 px-3 py-2.5 text-xs font-medium text-slate-700"
              >
                <input
                  type="checkbox"
                  checked={Boolean(homeEnv[field])}
                  onChange={() => toggleFlag(field)}
                  className="h-4 w-4 rounded border-slate-300 text-pine-700 focus:ring-pine-600"
                />
                <span>{label}</span>
              </label>
            ))}
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1">
              <label className="block text-xs font-medium text-slate-700">
                Optional Home Context (e.g., faces main road, balcony construction)
              </label>
              <input
                type="text"
                maxLength={240}
                value={homeEnv.notes || ""}
                onChange={(e) =>
                  updateHomeEnv((prev) => ({ ...prev, notes: e.target.value }))
                }
                placeholder="Optional details without personal names or medical records"
                className="mt-1 w-full rounded-xl border border-mist-200 px-3 py-2 text-sm focus:border-pine-600 focus:outline-none"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-pine-700 px-5 py-2.5 text-sm font-semibold text-white shadow-xs transition hover:bg-pine-800 disabled:opacity-60"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Analyzing Home &amp; Outdoor Air...</span>
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" />
                  <span>Generate Indoor Guide</span>
                </>
              )}
            </button>
          </div>
        </form>
      </section>

      {error && (
        <ErrorBanner
          title="Could not generate indoor recommendations"
          message={error}
          onRetry={handleGenerate}
        />
      )}

      {/* Recommendations Output */}
      {result && (
        <div className="space-y-5">
          {/* Summary & Verdict Card */}
          <section className="rounded-2xl border border-mist-200 bg-white p-5 shadow-xs">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-mist-100 pb-3">
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${
                    result.is_ai_generated
                      ? "border-pine-600/20 bg-pine-50 text-pine-800"
                      : "border-amber-200 bg-amber-50 text-amber-800"
                  }`}
                >
                  {result.is_ai_generated ? (
                    <>
                      <Bot className="h-3.5 w-3.5" />
                      Gemini AI ({result.model_used})
                    </>
                  ) : (
                    <>
                      <ShieldCheck className="h-3.5 w-3.5" />
                      Rule-Based Fallback
                    </>
                  )}
                </span>

                <span className="inline-flex items-center rounded-full border border-mist-200 bg-mist-50 px-2.5 py-0.5 text-[11px] font-semibold text-slate-700">
                  Indoor Sensors: Not Connected
                </span>

                {result.outdoor_conditions?.is_stale && (
                  <span className="inline-flex items-center gap-1 rounded-full border border-amber-300 bg-amber-50 px-2.5 py-0.5 text-[11px] font-semibold text-amber-900">
                    <AlertTriangle className="h-3 w-3" />
                    Stale Outdoor Telemetry
                  </span>
                )}

                {result.data_attribution?.outdoor_data_status === "unavailable" && (
                  <span className="inline-flex items-center gap-1 rounded-full border border-rose-300 bg-rose-50 px-2.5 py-0.5 text-[11px] font-semibold text-rose-900">
                    <AlertTriangle className="h-3 w-3" />
                    Outdoor Data Unavailable
                  </span>
                )}
              </div>

              <span className="inline-flex items-center gap-1 text-[11px] text-slate-500">
                <Clock className="h-3 w-3" />
                Outdoor Data: {result.data_timestamp}
              </span>
            </div>

            {result.fallback_reason && (
              <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50/70 px-3 py-1.5 text-xs text-amber-900">
                {result.fallback_reason}
              </p>
            )}

            <div className="mt-3 rounded-xl border border-pine-600/15 bg-pine-50/60 px-4 py-3">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-pine-800">
                Ventilation Verdict
              </p>
              <p className="mt-0.5 text-sm font-bold text-slate-900">
                {result.ventilation_verdict}
              </p>
            </div>

            <p className="mt-3 text-sm leading-relaxed text-slate-700">
              {result.summary}
            </p>
          </section>

          {/* Five Structured Recommendation Cards */}
          <section className="grid gap-4 md:grid-cols-2">
            {result.recommendations.map((rec, idx) => {
              const catMeta = CATEGORY_META[rec.category] || CATEGORY_META.pm25_reduction;
              const CatIcon = catMeta.icon;
              const prio = PRIORITY_STYLES[rec.priority] || PRIORITY_STYLES.medium;

              return (
                <article
                  key={`${rec.category}-${idx}`}
                  className="flex flex-col justify-between rounded-2xl border border-mist-200 bg-white p-5 shadow-xs"
                >
                  <div>
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span
                          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl ${catMeta.accent}`}
                        >
                          <CatIcon className="h-4 w-4" />
                        </span>
                        <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                          {rec.category_label || catMeta.label}
                        </span>
                      </div>

                      <span
                        className={`shrink-0 rounded-full border px-2.5 py-0.5 text-[10px] font-semibold ${prio.classes}`}
                      >
                        {prio.label}
                      </span>
                    </div>

                    <h4 className="mt-3 font-display text-sm font-bold text-slate-900">
                      {rec.title}
                    </h4>
                    <p className="mt-1.5 text-xs leading-relaxed text-slate-700">
                      {rec.description}
                    </p>

                    {Array.isArray(rec.action_steps) && rec.action_steps.length > 0 && (
                      <ul className="mt-3 space-y-1.5 rounded-xl bg-mist-50/70 p-3 text-xs text-slate-700">
                        {rec.action_steps.map((step, sIdx) => (
                          <li key={sIdx} className="flex gap-1.5">
                            <span className="font-bold text-pine-700">•</span>
                            <span>{step}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>

                  <div className="mt-3 space-y-1 border-t border-mist-100 pt-2.5 text-[11px] text-slate-600">
                    <p>
                      <span className="font-semibold text-slate-800">Why: </span>
                      {rec.reason}
                    </p>
                    <p>
                      <span className="font-semibold text-pine-800">
                        Expected benefit:{" "}
                      </span>
                      {rec.expected_benefit}
                    </p>
                  </div>
                </article>
              );
            })}
          </section>

          {/* Reasoning, Attribution, Limitations & Medical Disclaimer */}
          <section className="rounded-2xl border border-mist-200 bg-mist-50/70 p-5 text-xs leading-relaxed text-slate-700">
            <p>
              <span className="font-semibold text-slate-900">Reasoning: </span>
              {result.reasoning}
            </p>
            {result.data_attribution && (
              <p className="mt-2">
                <span className="font-semibold text-slate-900">
                  Data Attribution:{" "}
                </span>
                {result.data_attribution.indoor_sensor_note} (Outdoor status:{" "}
                {result.data_attribution.outdoor_data_status}, kind:{" "}
                {result.data_attribution.outdoor_telemetry_kind}).
              </p>
            )}
            {Array.isArray(result.limitations) && result.limitations.length > 0 && (
              <div className="mt-2.5">
                <p className="font-semibold text-slate-900">
                  Limitations &amp; Uncertainty:
                </p>
                <ul className="mt-1 space-y-1 text-slate-600">
                  {result.limitations.map((lim, idx) => (
                    <li key={idx} className="flex gap-1.5">
                      <span>•</span>
                      <span>{lim}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <p className="mt-3 rounded-xl border border-mist-200 bg-white px-3.5 py-2 text-[11px] font-medium text-slate-600">
              {result.disclaimer}
            </p>
          </section>
        </div>
      )}
    </div>
  );
}
