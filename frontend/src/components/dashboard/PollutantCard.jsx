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
        <p className="mt-1 text-[11px] text-slate-500">
          Current model estimate · Not a ground-station observation
        </p>

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
          <div className="space-y-1">
            <p className="text-[11px] font-medium text-slate-600">
              WHO 24-hour guideline reference: {guideline} {unit}
            </p>
            <p className="text-[10px] leading-relaxed text-slate-500">
              This is a 24-hour average reference. The current model estimate above
              is not directly comparable and should not be classified as above or
              within this guideline.
            </p>
          </div>
        ) : (
          <span className="text-[11px] text-slate-400">
            Reference threshold not configured
          </span>
        )}
      </div>
    </article>
  );
}
