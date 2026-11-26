import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Activity, AlertCircle, Compass, Clock } from "lucide-react";
import DataStatusBadge from "../common/DataStatusBadge";
import { EmptyState, LoadingCardSkeleton } from "../common/StateFeedback";
import {
  formatHourLabel,
  formatTimestamp,
  getAqiAppearance,
} from "../../utils/airQuality";

export default function AirQualityOverview({
  airQuality,
  loading,
  error,
  onRetry,
}) {
  if (loading) {
    return <LoadingCardSkeleton lines={6} />;
  }

  if (error && !airQuality) {
    return (
      <section className="rounded-2xl border border-rose-200 bg-white p-6 shadow-xs">
        <EmptyState
          icon={AlertCircle}
          title="Air quality overview unavailable"
          description={error}
          action={
            onRetry && (
              <button
                type="button"
                onClick={onRetry}
                className="rounded-xl bg-pine-700 px-4 py-2 text-xs font-semibold text-white hover:bg-pine-800"
              >
                Try Again
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
    us_aqi: usAqi,
    european_aqi: europeanAqi,
    fetched_at: fetchedAt,
    cached_at: cachedAt,
    cache_expires_at: cacheExpiresAt,
    hourly_trend: hourlyTrend = [],
    error_detail: errorDetail,
    source,
  } = airQuality;

  const appearance = getAqiAppearance(usAqi, dataStatus);
  const chartData = hourlyTrend
    .filter((pt) => pt.pm2_5 !== null || pt.us_aqi !== null)
    .map((pt) => ({
      hour: formatHourLabel(pt.time),
      usAqi: pt.us_aqi,
      pm25: pt.pm2_5,
    }));

  const isUnavailable = dataStatus === "unavailable" || usAqi === null;

  return (
    <section
      aria-label="Air Quality Overview"
      className={`rounded-2xl border border-mist-200 bg-gradient-to-br ${appearance.panelTint} p-6 shadow-xs`}
    >
      {/* Top row: location + status */}
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
          <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
            <span>
              Coordinates: {location.latitude.toFixed(3)}, {location.longitude.toFixed(3)}
            </span>
            <span>·</span>
            <span>Source: {source}</span>
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
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
        {/* AQI Headline Metric */}
        <div className="flex flex-col justify-between rounded-2xl border border-mist-200 bg-white/90 p-5 lg:col-span-5">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                US Air Quality Index
              </span>
              <span
                className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold ${appearance.badgeBg}`}
              >
                {appearance.category}
              </span>
            </div>

            <div className="mt-4 flex items-baseline gap-3">
              <span
                className={`font-display text-5xl font-bold tracking-tight ${
                  isUnavailable ? "text-slate-400" : "text-slate-900"
                }`}
              >
                {isUnavailable ? "—" : Math.round(usAqi)}
              </span>
              <div className="text-xs text-slate-500">
                <p className="font-medium text-slate-700">US EPA Scale</p>
                <p>
                  European AQI:{" "}
                  <strong className="text-slate-800">
                    {europeanAqi !== null && europeanAqi !== undefined
                      ? Math.round(europeanAqi)
                      : "Unavailable"}
                  </strong>
                </p>
              </div>
            </div>

            <p className="mt-4 text-xs leading-relaxed text-slate-600">
              {errorDetail && isUnavailable ? errorDetail : appearance.summary}
            </p>
          </div>

          <div className="mt-5 flex items-center justify-between border-t border-mist-100 pt-3 text-[11px] text-slate-500">
            <span className="inline-flex items-center gap-1.5">
              <Activity className="h-3.5 w-3.5 text-pine-700" />
              {dataStatus === "live"
                ? "Verified live reading"
                : dataStatus === "cached"
                  ? "Served from TTL cache"
                  : "No live or cached reading"}
            </span>
            {fetchedAt && <span>Timestamp: {formatTimestamp(fetchedAt)}</span>}
          </div>
        </div>

        {/* 24-hour trend chart */}
        <div className="rounded-2xl border border-mist-200 bg-white/90 p-5 lg:col-span-7">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">
                24-Hour PM2.5 &amp; US AQI Trend
              </h3>
              <p className="text-xs text-slate-500">
                Hourly atmospheric trajectory from Open-Meteo
              </p>
            </div>
            <DataStatusBadge status={dataStatus} compact />
          </div>

          {chartData.length === 0 ? (
            <div className="flex h-52 items-center justify-center rounded-xl border border-dashed border-mist-200 bg-mist-50/50 px-4 text-center">
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
            <div className="h-52 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  data={chartData}
                  margin={{ top: 8, right: 10, left: -16, bottom: 0 }}
                >
                  <defs>
                    <linearGradient id="pm25Gradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#0F766E" stopOpacity={0.28} />
                      <stop offset="95%" stopColor="#0F766E" stopOpacity={0.02} />
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
                  <Tooltip
                    contentStyle={{
                      borderRadius: "12px",
                      borderColor: "#DCE6DF",
                      fontSize: "12px",
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="pm25"
                    name="PM2.5 (μg/m³)"
                    stroke="#0F766E"
                    strokeWidth={2}
                    fill="url(#pm25Gradient)"
                    connectNulls
                  />
                  <Area
                    type="monotone"
                    dataKey="usAqi"
                    name="US AQI"
                    stroke="#F59E0B"
                    strokeWidth={1.75}
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
