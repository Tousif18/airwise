import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  Clock,
  Compass,
  Info,
} from "lucide-react";
import DataStatusBadge from "../common/DataStatusBadge";
import { EmptyState, LoadingCardSkeleton } from "../common/StateFeedback";
import {
  formatHourLabel,
  formatObservationTime,
  formatTimestamp,
  getAqiAppearance,
  getCpcbAqiAppearance,
  getValueKindMeta,
} from "../../utils/airQuality";
import { classifyTelemetryFeedback } from "../../utils/requestControl";

function TrendTooltip({ active, payload, label }) {
  if (!active || !payload || payload.length === 0) return null;
  const row = payload[0]?.payload;
  const kindMeta = getValueKindMeta(row?.valueKind);

  return (
    <div className="rounded-xl border border-mist-200 bg-white px-3 py-2 text-xs shadow-md">
      <div className="flex items-center justify-between gap-3 border-b border-mist-100 pb-1">
        <span className="font-semibold text-slate-900">{label}</span>
        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${kindMeta.classes}`}>
          {kindMeta.label}
        </span>
      </div>
      <div className="mt-1.5 space-y-1">
        {row?.pm25 !== null && row?.pm25 !== undefined && (
          <p className="text-slate-700">
            PM2.5: <strong className="text-pine-800">{row.pm25} μg/m³</strong>
          </p>
        )}
        {row?.usAqi !== null && row?.usAqi !== undefined && (
          <p className="text-slate-700">
            US AQI: <strong className="text-amber-700">{Math.round(row.usAqi)}</strong>
          </p>
        )}
      </div>
    </div>
  );
}

export default function AirQualityOverview({
  airQuality,
  loading,
  error,
  refreshCooldownSeconds = 0,
  onRetry,
}) {
  if (loading) {
    return <LoadingCardSkeleton lines={6} />;
  }

  if (error && !airQuality) {
    const feedback = classifyTelemetryFeedback({ airQuality: null, error });
    return (
      <section className="rounded-2xl border border-rose-200 bg-white p-6 shadow-xs">
        <EmptyState
          icon={AlertCircle}
          title={feedback.title}
          description={feedback.message}
          action={
            onRetry && (
              <button
                type="button"
                disabled={refreshCooldownSeconds > 0}
                onClick={onRetry}
                className="rounded-xl bg-pine-700 px-4 py-2 text-xs font-semibold text-white hover:bg-pine-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {refreshCooldownSeconds > 0
                  ? `Wait ${refreshCooldownSeconds}s`
                  : "Try Again"}
              </button>
            )
          }
        />
      </section>
    );
  }

  if (!airQuality) {
    return (
      <EmptyState
        icon={Compass}
        title="Select a location"
        description="Choose a city above to inspect live Open-Meteo air quality telemetry."
      />
    );
  }

  const {
    location,
    data_status: dataStatus,
    telemetry_kind: telemetryKind = "estimated",
    observation_time: observationTime,
    us_aqi: usAqi,
    european_aqi: europeanAqi,
    indian_aqi: indianAqi,
    fetched_at: fetchedAt,
    cached_at: cachedAt,
    cache_expires_at: cacheExpiresAt,
    is_stale: isStale,
    stale_reason: staleReason,
    api_warning: apiWarning,
    hourly_trend: hourlyTrend = [],
    error_detail: errorDetail,
    source,
  } = airQuality;

  const usAppearance = getAqiAppearance(usAqi, dataStatus);
  const cpcbAppearance = getCpcbAqiAppearance(indianAqi?.aqi, indianAqi?.status);
  const telemetryMeta = getValueKindMeta(telemetryKind);

  const panelTint =
    indianAqi?.status !== "unavailable" && indianAqi?.aqi !== null
      ? cpcbAppearance.panelTint
      : usAppearance.panelTint;

  // Build chart series separating Estimated (past/current model) and Forecast (upcoming)
  const validPoints = hourlyTrend.filter(
    (pt) => pt.pm2_5 !== null || pt.us_aqi !== null
  );
  const firstForecastIdx = validPoints.findIndex((pt) => pt.value_kind === "forecast");
  const chartData = validPoints.map((pt, idx) => {
    const isForecast = pt.value_kind === "forecast";
    const isBridgePoint = firstForecastIdx > 0 && idx === firstForecastIdx - 1;
    return {
      hour: formatHourLabel(pt.time),
      valueKind: pt.value_kind || "estimated",
      pm25: pt.pm2_5,
      pm25Estimated: !isForecast ? pt.pm2_5 : null,
      pm25Forecast: isForecast || isBridgePoint ? pt.pm2_5 : null,
      usAqi: pt.us_aqi,
    };
  });

  const isCpcbUnavailable =
    !indianAqi || indianAqi.status === "unavailable" || indianAqi.aqi === null;
  const isUsUnavailable = dataStatus === "unavailable" || usAqi === null;
  const feedback = classifyTelemetryFeedback({
    airQuality,
    error: error ? { message: error } : null,
  });

  return (
    <section
      aria-label="Air Quality Overview"
      className={`rounded-2xl border border-mist-200 bg-gradient-to-br ${panelTint} p-6 shadow-xs`}
    >
      {/* Distinct warning banner for rate limit, stale cache, or unavailable telemetry */}
      {(feedback.kind === "rate_limited" ||
        feedback.kind === "no_cached_data" ||
        feedback.kind === "stale_cached" ||
        isStale ||
        apiWarning ||
        dataStatus === "unavailable") && (
        <div
          role="status"
          className={`mb-5 flex flex-col gap-2 rounded-xl border px-4 py-3 text-xs sm:flex-row sm:items-center sm:justify-between ${
            feedback.kind === "rate_limited" ||
            feedback.kind === "no_cached_data" ||
            dataStatus === "unavailable"
              ? "border-rose-200 bg-rose-50/90 text-rose-900"
              : "border-amber-200 bg-amber-50/90 text-amber-900"
          }`}
        >
          <div className="flex items-start gap-2.5">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <div className="space-y-0.5">
              <p className="font-semibold">{feedback.title}</p>
              <p className="opacity-90">{feedback.message}</p>
            </div>
          </div>
          {onRetry && (
            <button
              type="button"
              disabled={refreshCooldownSeconds > 0}
              onClick={onRetry}
              className="self-start rounded-lg border border-current/25 bg-white px-3 py-1 font-semibold transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 sm:self-auto"
            >
              {refreshCooldownSeconds > 0
                ? `Cooldown (${refreshCooldownSeconds}s)`
                : "Retry Live Fetch"}
            </button>
          )}
        </div>
      )}

      {/* Top row: location + source + timestamps + freshness */}
      <div className="flex flex-col gap-3 border-b border-mist-200/80 pb-5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="font-display text-xl font-bold text-slate-900 sm:text-2xl">
              {location.name}
            </h2>
            <span className="text-sm text-slate-500">
              {[location.region, location.country].filter(Boolean).join(", ")}
            </span>
          </div>
          <p className="mt-1 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-xs text-slate-500">
            <span>
              Coordinates: {location.latitude.toFixed(3)}, {location.longitude.toFixed(3)}
            </span>
            <span>·</span>
            <span>
              Source: <strong className="font-medium text-slate-700">{source}</strong>
            </span>
            {observationTime && (
              <>
                <span>·</span>
                <span>
                  Model Time:{" "}
                  <strong className="font-medium text-slate-700">
                    {formatObservationTime(observationTime)}
                  </strong>
                </span>
              </>
            )}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span
            className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium ${telemetryMeta.classes}`}
            title="Open-Meteo provides modeled atmospheric estimates rather than direct ground sensor observations."
          >
            {telemetryMeta.label} · Model
          </span>
          <DataStatusBadge
            status={dataStatus}
            detail={
              dataStatus === "cached"
                ? `Cached ${formatTimestamp(cachedAt)}`
                : dataStatus === "live"
                  ? `Fetched ${formatTimestamp(fetchedAt)}`
                  : "Upstream unreachable"
            }
          />
          {dataStatus === "cached" && cacheExpiresAt && (
            <span className="inline-flex items-center gap-1 text-[11px] text-slate-500">
              <Clock className="h-3 w-3" />
              Expires {formatTimestamp(cacheExpiresAt)}
            </span>
          )}
        </div>
      </div>

      {/* Main metrics + 24h trend chart */}
      <div className="mt-6 grid gap-6 lg:grid-cols-12">
        {/* AQI Scales Panel */}
        <div className="flex flex-col justify-between gap-4 rounded-2xl border border-mist-200 bg-white/95 p-5 lg:col-span-5">
          {/* Indian CPCB AQI Primary Block */}
          <div>
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-pine-800">
                Indian CPCB AQI (NAQI)
              </span>
              <span
                className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold ${cpcbAppearance.badgeBg}`}
              >
                {indianAqi?.category || "Unavailable"}
              </span>
            </div>

            <div className="mt-3 flex items-baseline gap-3">
              <span
                className={`font-display text-5xl font-bold tracking-tight ${
                  isCpcbUnavailable ? "text-slate-400" : "text-slate-900"
                }`}
              >
                {isCpcbUnavailable ? "Unavailable" : indianAqi.aqi}
              </span>
              {!isCpcbUnavailable && (
                <div className="text-xs text-slate-600">
                  <p className="font-semibold text-slate-800">
                    Prominent: {indianAqi.prominent_pollutant}
                  </p>
                  <p>
                    Valid pollutants: {indianAqi.valid_pollutant_count} (min 3 w/ PM)
                  </p>
                </div>
              )}
            </div>

            <p className="mt-3 flex items-start gap-1.5 rounded-xl bg-mist-50 p-2.5 text-[11px] leading-relaxed text-slate-600">
              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-pine-700" />
              <span>
                {isCpcbUnavailable
                  ? indianAqi?.unavailable_reason ||
                    "Required pollutant averages are missing to compute Indian CPCB AQI."
                  : indianAqi.methodology_note}
              </span>
            </p>
          </div>

          {/* US AQI & European AQI Comparison Cards */}
          <div className="grid grid-cols-2 gap-3 border-t border-mist-100 pt-4">
            <div className="rounded-xl border border-mist-200 bg-mist-50/60 p-3">
              <div className="flex items-center justify-between gap-1">
                <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  US AQI
                </span>
                <span
                  className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${usAppearance.badgeBg}`}
                >
                  {usAppearance.category}
                </span>
              </div>
              <p
                className={`mt-1.5 font-display text-2xl font-bold ${
                  isUsUnavailable ? "text-slate-400" : "text-slate-900"
                }`}
              >
                {isUsUnavailable ? "Unavailable" : Math.round(usAqi)}
              </p>
              <p className="text-[11px] text-slate-500">US EPA Scale · Open-Meteo</p>
            </div>

            <div className="rounded-xl border border-mist-200 bg-mist-50/60 p-3">
              <div className="flex items-center justify-between gap-1">
                <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  European AQI
                </span>
                <span className="rounded-full border border-mist-200 bg-white px-2 py-0.5 text-[10px] font-semibold text-slate-600">
                  EAQI
                </span>
              </div>
              <p
                className={`mt-1.5 font-display text-2xl font-bold ${
                  europeanAqi === null || europeanAqi === undefined
                    ? "text-slate-400"
                    : "text-slate-900"
                }`}
              >
                {europeanAqi !== null && europeanAqi !== undefined
                  ? Math.round(europeanAqi)
                  : "Unavailable"}
              </p>
              <p className="text-[11px] text-slate-500">EU Index · Open-Meteo</p>
            </div>
          </div>

          <div className="flex items-center justify-between border-t border-mist-100 pt-3 text-[11px] text-slate-500">
            <span className="inline-flex items-center gap-1.5">
              <Activity className="h-3.5 w-3.5 text-pine-700" />
              {dataStatus === "live"
                ? "Verified live API fetch"
                : dataStatus === "cached"
                  ? isStale
                    ? "Stale TTL cache"
                    : "Served from TTL cache"
                  : "No live or cached reading"}
            </span>
            {fetchedAt && <span>Fetched: {formatTimestamp(fetchedAt)} UTC</span>}
          </div>
        </div>

        {/* 24-hour trend chart */}
        <div className="rounded-2xl border border-mist-200 bg-white/95 p-5 lg:col-span-7">
          <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">
                24-Hour PM2.5 &amp; US AQI Trajectory
              </h3>
              <p className="text-xs text-slate-500">
                Distinguishes Open-Meteo model estimates from upcoming forecast hours
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-1.5 text-[10px] font-semibold">
              <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-emerald-800">
                Observed: Ground N/A
              </span>
              <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-amber-800">
                Estimated (Model)
              </span>
              <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-indigo-800">
                Forecast (Upcoming)
              </span>
            </div>
          </div>

          {chartData.length === 0 ? (
            <div className="flex h-60 items-center justify-center rounded-xl border border-dashed border-mist-200 bg-mist-50/50 px-4 text-center">
              <div>
                <p className="text-sm font-medium text-slate-700">
                  Hourly trend unavailable
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  {errorDetail ||
                    "No hourly air quality series returned for this location."}
                </p>
              </div>
            </div>
          ) : (
            <div className="h-60 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  data={chartData}
                  margin={{ top: 8, right: 10, left: -16, bottom: 0 }}
                >
                  <defs>
                    <linearGradient id="pm25EstimatedGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#0F766E" stopOpacity={0.28} />
                      <stop offset="95%" stopColor="#0F766E" stopOpacity={0.02} />
                    </linearGradient>
                    <linearGradient id="pm25ForecastGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#4F46E5" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="#4F46E5" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E2EBE6" />
                  <XAxis
                    dataKey="hour"
                    tick={{ fontSize: 11, fill: "#64748B" }}
                    tickLine={false}
                    axisLine={false}
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: "#64748B" }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <Tooltip content={<TrendTooltip />} />
                  <Area
                    type="monotone"
                    dataKey="pm25Estimated"
                    name="PM2.5 Estimated (μg/m³)"
                    stroke="#0F766E"
                    strokeWidth={2}
                    fill="url(#pm25EstimatedGrad)"
                    connectNulls={false}
                  />
                  <Area
                    type="monotone"
                    dataKey="pm25Forecast"
                    name="PM2.5 Forecast (μg/m³)"
                    stroke="#4F46E5"
                    strokeWidth={2}
                    strokeDasharray="5 4"
                    fill="url(#pm25ForecastGrad)"
                    connectNulls={false}
                  />
                  <Area
                    type="monotone"
                    dataKey="usAqi"
                    name="US AQI"
                    stroke="#F59E0B"
                    strokeWidth={1.5}
                    fill="none"
                    connectNulls
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
