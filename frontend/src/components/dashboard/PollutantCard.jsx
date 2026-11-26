import DataStatusBadge from "../common/DataStatusBadge";

export default function PollutantCard({ pollutant }) {
  const {
    formula,
    label,
    value,
    unit,
    status,
    guideline_24h: guideline,
    description,
  } = pollutant;

  const isUnavailable = status === "unavailable" || value === null || value === undefined;
  const ratio =
    !isUnavailable && guideline ? Math.min(100, Math.round((value / guideline) * 100)) : 0;
  const exceedsGuideline = !isUnavailable && guideline ? value > guideline : false;

  return (
    <article className="flex flex-col justify-between rounded-2xl border border-mist-200 bg-white p-4 shadow-xs transition hover:border-pine-600/30">
      <div>
        <div className="flex items-start justify-between gap-2">
          <div>
            <span className="inline-flex items-center rounded-lg bg-mist-100 px-2 py-0.5 text-xs font-bold text-pine-900">
              {formula}
            </span>
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

        <p className="mt-2 text-xs leading-relaxed text-slate-500">{description}</p>
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
