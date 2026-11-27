import { useState } from "react";
import {
  AlertTriangle,
  Bot,
  ChevronDown,
  ChevronUp,
  Clock,
  Home,
  Info,
  Leaf,
  ShieldCheck,
  Sun,
} from "lucide-react";

const PRIORITY_STYLES = {
  high: {
    label: "High Priority",
    classes: "bg-rose-50 text-rose-800 border-rose-200",
  },
  medium: {
    label: "Medium Priority",
    classes: "bg-amber-50 text-amber-800 border-amber-200",
  },
  low: {
    label: "Low Priority",
    classes: "bg-emerald-50 text-emerald-800 border-emerald-200",
  },
};

const RISK_STYLES = {
  unknown: "bg-slate-100 text-slate-700 border-slate-200",
  low: "bg-emerald-50 text-emerald-800 border-emerald-200",
  moderate: "bg-amber-50 text-amber-800 border-amber-200",
  sensitive_caution: "bg-orange-50 text-orange-800 border-orange-200",
  high: "bg-rose-50 text-rose-800 border-rose-200",
  very_high: "bg-purple-50 text-purple-800 border-purple-200",
  hazardous: "bg-red-100 text-red-900 border-red-300",
};

function AqiPill({ scale }) {
  if (!scale) return null;
  const available = scale.status !== "unavailable" && scale.value !== null && scale.value !== undefined;
  return (
    <div className="rounded-xl border border-mist-200 bg-mist-50/70 px-3 py-2">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
        {scale.standard_name}
      </p>
      <p className="mt-0.5 text-sm font-bold text-slate-900">
        {available ? `${scale.value} · ${scale.category}` : "Unavailable"}
      </p>
      {scale.prominent_pollutant && (
        <p className="text-[11px] text-slate-600">
          Prominent: {scale.prominent_pollutant}
        </p>
      )}
    </div>
  );
}

export default function RecommendationCards({ data }) {
  const [showReasoning, setShowReasoning] = useState(true);

  if (!data) return null;

  const isAi = Boolean(data.is_ai_generated);
  const conditions = data.current_conditions;
  const riskClass = RISK_STYLES[conditions?.risk_level] || RISK_STYLES.unknown;

  return (
    <div className="space-y-4">
      {/* Header status + summary */}
      <div className="rounded-2xl border border-mist-200 bg-white p-4 shadow-xs">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-mist-100 pb-3">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${
                isAi
                  ? "border-pine-600/20 bg-pine-50 text-pine-800"
                  : "border-amber-200 bg-amber-50 text-amber-800"
              }`}
            >
              {isAi ? (
                <>
                  <Bot className="h-3.5 w-3.5" />
                  Gemini AI ({data.model_used || "gemini"})
                </>
              ) : (
                <>
                  <ShieldCheck className="h-3.5 w-3.5" />
                  Rule-Based Fallback
                </>
              )}
            </span>

            {conditions?.risk_level && (
              <span
                className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-semibold capitalize ${riskClass}`}
              >
                Risk: {conditions.risk_level.replace(/_/g, " ")}
              </span>
            )}

            {conditions?.is_stale && (
              <span className="inline-flex items-center gap-1 rounded-full border border-amber-300 bg-amber-50 px-2.5 py-0.5 text-[11px] font-semibold text-amber-900">
                <AlertTriangle className="h-3 w-3" />
                Stale Data
              </span>
            )}
          </div>

          <span className="inline-flex items-center gap-1 text-[11px] text-slate-500">
            <Clock className="h-3 w-3" />
            Data: {data.data_timestamp || "Unavailable"}
          </span>
        </div>

        {data.fallback_reason && (
          <p className="mt-2.5 rounded-xl border border-amber-200 bg-amber-50/70 px-3 py-1.5 text-xs text-amber-900">
            {data.fallback_reason}
          </p>
        )}

        <p className="mt-3 text-sm leading-relaxed text-slate-800">{data.summary}</p>

        {/* Separate AQI Standards */}
        {conditions && (
          <div className="mt-3 grid gap-2 sm:grid-cols-3">
            <AqiPill scale={conditions.us_aqi} />
            <AqiPill scale={conditions.indian_cpcb_aqi} />
            <AqiPill scale={conditions.european_aqi} />
          </div>
        )}
      </div>

      {/* Recommendation cards */}
      {Array.isArray(data.recommendations) && data.recommendations.length > 0 && (
        <div className="grid gap-3 md:grid-cols-2">
          {data.recommendations.map((rec, idx) => {
            const prio = PRIORITY_STYLES[rec.priority] || PRIORITY_STYLES.medium;
            return (
              <article
                key={`${rec.title}-${idx}`}
                className="flex flex-col justify-between rounded-2xl border border-mist-200 bg-white p-4 shadow-xs"
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <h4 className="text-sm font-bold text-slate-900">{rec.title}</h4>
                    <span
                      className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold ${prio.classes}`}
                    >
                      {prio.label}
                    </span>
                  </div>
                  <p className="mt-2 text-xs leading-relaxed text-slate-700">
                    {rec.description}
                  </p>
                </div>

                <div className="mt-3 space-y-1 border-t border-mist-100 pt-2.5 text-[11px] text-slate-600">
                  <p>
                    <span className="font-semibold text-slate-800">Why: </span>
                    {rec.reason}
                  </p>
                  <p>
                    <span className="font-semibold text-pine-800">Expected benefit: </span>
                    {rec.expected_benefit}
                  </p>
                </div>
              </article>
            );
          })}
        </div>
      )}

      {/* Indoor / Outdoor / Sustainable action columns */}
      <div className="grid gap-3 md:grid-cols-3">
        <div className="rounded-2xl border border-mist-200 bg-white p-4 shadow-xs">
          <div className="flex items-center gap-2 text-xs font-bold text-slate-900">
            <Home className="h-4 w-4 text-pine-700" />
            <span>Indoor Actions</span>
          </div>
          <ul className="mt-2.5 space-y-1.5 text-xs leading-relaxed text-slate-600">
            {(data.indoor_actions || []).map((item, idx) => (
              <li key={idx} className="flex gap-1.5">
                <span className="text-pine-700">•</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-2xl border border-mist-200 bg-white p-4 shadow-xs">
          <div className="flex items-center gap-2 text-xs font-bold text-slate-900">
            <Sun className="h-4 w-4 text-amber-600" />
            <span>Outdoor Actions</span>
          </div>
          <ul className="mt-2.5 space-y-1.5 text-xs leading-relaxed text-slate-600">
            {(data.outdoor_actions || []).map((item, idx) => (
              <li key={idx} className="flex gap-1.5">
                <span className="text-amber-600">•</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-2xl border border-mist-200 bg-white p-4 shadow-xs">
          <div className="flex items-center gap-2 text-xs font-bold text-slate-900">
            <Leaf className="h-4 w-4 text-emerald-700" />
            <span>Sustainable Alternatives</span>
          </div>
          <ul className="mt-2.5 space-y-1.5 text-xs leading-relaxed text-slate-600">
            {(data.sustainable_alternatives || []).map((item, idx) => (
              <li key={idx} className="flex gap-1.5">
                <span className="text-emerald-700">•</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Reasoning, Impact, Limitations */}
      <div className="rounded-2xl border border-mist-200 bg-mist-50/70 p-4">
        <button
          type="button"
          aria-expanded={showReasoning}
          aria-controls="recommendation-explanation"
          onClick={() => setShowReasoning((prev) => !prev)}
          className="flex w-full items-center justify-between text-left"
        >
          <span className="flex items-center gap-2 text-xs font-bold text-slate-900">
            <Info className="h-4 w-4 text-pine-700" />
            Explanation, Environmental Impact &amp; Data Limitations
          </span>
          {showReasoning ? (
            <ChevronUp className="h-4 w-4 text-slate-500" />
          ) : (
            <ChevronDown className="h-4 w-4 text-slate-500" />
          )}
        </button>

        {showReasoning && (
          <div
            id="recommendation-explanation"
            className="mt-3 space-y-2.5 border-t border-mist-200 pt-3 text-xs leading-relaxed text-slate-700"
          >
            <p>
              <span className="font-semibold text-slate-900">Reasoning: </span>
              {data.reasoning}
            </p>
            <p>
              <span className="font-semibold text-slate-900">Estimated Environmental Impact: </span>
              {data.estimated_environmental_impact}
            </p>
            {Array.isArray(data.limitations) && data.limitations.length > 0 && (
              <div>
                <p className="font-semibold text-slate-900">Limitations &amp; Uncertainty:</p>
                <ul className="mt-1 space-y-1 text-slate-600">
                  {data.limitations.map((lim, idx) => (
                    <li key={idx} className="flex gap-1.5">
                      <span>•</span>
                      <span>{lim}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {data.disclaimer && (
              <p className="text-[11px] italic text-slate-500">{data.disclaimer}</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
