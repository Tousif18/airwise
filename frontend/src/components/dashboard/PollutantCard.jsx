import DataStatusBadge from "../common/DataStatusBadge";
import { getValueKindMeta } from "../../utils/airQuality";

export default function PollutantCard({ pollutant }) {
  const {
    formula,
    label,
    value,
    unit,
    status,
    value_kind: valueKind = "estimated",
    guideline_24h: guideline,
    description,
    cpcb_sub_index: cpcbSubIndex,
    cpcb_category: cpcbCategory,
    cpcb_avg_value: cpcbAvgValue,
    cpcb_avg_unit: cpcbAvgUnit,
    cpcb_averaging_period: cpcbAveragingPeriod,
  } = pollutant;

  const isUnavailable = status === "unavailable" || value === null || value === undefined;
  const ratio =
    !isUnavailable && guideline ? Math.min(100, Math.round((value / guideline) * 100)) : 0;
  const exceedsGuideline = !isUnavailable && guideline ? value > guideline : false;
  const kindMeta = getValueKindMeta(valueKind);

  return (
    <article className="flex flex-col justify-between rounded-2xl border border-mist-200 bg-white p-4 shadow-xs transition hover:border-pine-600/30">
      <div>
        <div className="flex items-start justify-between gap-2">
          <div>
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="inline-flex items-center rounded-lg bg-mist-100 px-2 py-0.5 text-xs font-bold text-pine-900">
                {formula}
              </span>
              <span
                className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold ${kindMeta.classes}`}
              >
                {kindMeta.label}
              </span>
            </div>
            <h3 className="mt-1.5 text-sm font-semibold text-slate-900">{label}</h3>
          </div>
          <DataStatusBadge status={status} compact />
        </div>

        <div className="mt-4 flex items-baseline gap-1.5">
          <span
            className={`font-display text-2xl font-bold ${
              isUnavailable ? "text-slate-400" : "text-slate-900"
            }`}
          >
            {isUnavailable ? "Unavailable" : value}
          </span>
          {!isUnavailable && (
            <span className="text-xs font-medium text-slate-500">{unit}</span>
          )}
        </div>

        {/* CPCB Sub-Index pill */}
        <div className="mt-2.5 rounded-xl bg-mist-50 px-3 py-2 text-[11px]">
          {cpcbSubIndex !== null && cpcbSubIndex !== undefined ? (
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium text-slate-600">
                CPCB Sub-Index ({cpcbAveragingPeriod}):
              </span>
              <span className="font-semibold text-pine-900">
                {cpcbSubIndex} · {cpcbCategory}
              </span>
            </div>
          ) : (
            <span className="text-slate-500">
              CPCB sub-index: Unavailable (insufficient averaging window)
            </span>
          )}
          {cpcbAvgValue !== null && cpcbAvgValue !== undefined && (
            <p className="mt-0.5 text-[10px] text-slate-500">
              Window mean: {cpcbAvgValue} {cpcbAvgUnit}
            </p>
          )}
        </div>

        <p className="mt-2.5 text-xs leading-relaxed text-slate-500">{description}</p>
      </div>

      <div className="mt-4 border-t border-mist-100 pt-3">
        {guideline ? (
          <>
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-slate-500">
                WHO 24h guideline: {guideline} {unit}
              </span>
              {!isUnavailable && (
                <span
                  className={`font-semibold ${
                    exceedsGuideline ? "text-amber-700" : "text-emerald-700"
                  }`}
                >
                  {exceedsGuideline ? "Above guideline" : "Within guideline"}
                </span>
              )}
            </div>
            <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-mist-100">
              <div
                className={`h-full rounded-full transition-all ${
                  isUnavailable
                    ? "w-0 bg-slate-300"
                    : exceedsGuideline
                      ? "bg-amber-500"
                      : "bg-emerald-500"
                }`}
                style={{ width: isUnavailable ? "0%" : `${Math.max(8, ratio)}%` }}
              />
            </div>
          </>
        ) : (
          <span className="text-[11px] text-slate-400">
            Reference threshold not configured
          </span>
        )}
      </div>
    </article>
  );
}
