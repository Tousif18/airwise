import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Bike,
  Calendar,
  Car,
  Info,
  Leaf,
  PlusCircle,
  RotateCcw,
  Route,
  Settings2,
  TrainFront,
  Trash2,
  Users,
} from "lucide-react";
import { EmptyState } from "../components/common/StateFeedback";
import {
  ACTIVITY_TYPES,
  DEFAULT_EMISSION_ASSUMPTIONS,
  calculateActivityImpact,
  getTodayIsoDate,
  loadEmissionAssumptions,
  loadImpactRecords,
  saveEmissionAssumptions,
  saveImpactRecords,
  summarizeImpact,
  validateActivityInput,
  validateAssumptionsInput,
} from "../utils/emissions";

const ACTIVITY_META = {
  public_transport: {
    icon: TrainFront,
    badge: "bg-sky-50 text-sky-800 border-sky-200",
  },
  carpooling: {
    icon: Users,
    badge: "bg-indigo-50 text-indigo-800 border-indigo-200",
  },
  vehicle_avoided: {
    icon: Car,
    badge: "bg-amber-50 text-amber-800 border-amber-200",
  },
  walking_cycling: {
    icon: Bike,
    badge: "bg-emerald-50 text-emerald-800 border-emerald-200",
  },
};

function ImpactTooltip({ active, payload, label }) {
  if (!active || !payload || payload.length === 0) return null;
  const row = payload[0]?.payload;
  return (
    <div className="rounded-xl border border-mist-200 bg-white px-3 py-2 text-xs shadow-md">
      <p className="font-semibold text-slate-900">{row?.date || row?.label || label}</p>
      <div className="mt-1 space-y-0.5 text-slate-700">
        <p>
          Est. CO₂ avoided:{" "}
          <strong className="text-pine-800">{row?.co2AvoidedKg ?? 0} kg</strong>
        </p>
        <p>
          Distance: <strong>{row?.distanceKm ?? 0} km</strong>
        </p>
        <p>
          Trips: <strong>{row?.trips ?? 0}</strong>
        </p>
      </div>
    </div>
  );
}

export default function EnvironmentalImpactPage({ onBackToDashboard }) {
  const [records, setRecords] = useState(() => loadImpactRecords());
  const [assumptions, setAssumptions] = useState(() => loadEmissionAssumptions());

  const [activityType, setActivityType] = useState("public_transport");
  const [trips, setTrips] = useState("2");
  const [distanceKm, setDistanceKm] = useState("6");
  const [date, setDate] = useState(() => getTodayIsoDate());
  const [formErrors, setFormErrors] = useState({});

  const [showAssumptions, setShowAssumptions] = useState(false);
  const [assumptionsDraft, setAssumptionsDraft] = useState(() =>
    loadEmissionAssumptions()
  );
  const [assumptionsErrors, setAssumptionsErrors] = useState({});
  const [historyScope, setHistoryScope] = useState("weekly"); // "weekly" | "all"

  useEffect(() => {
    saveImpactRecords(records);
  }, [records]);

  useEffect(() => {
    saveEmissionAssumptions(assumptions);
  }, [assumptions]);

  const todayStr = getTodayIsoDate();
  const summary = useMemo(
    () => summarizeImpact(records, assumptions, todayStr),
    [records, assumptions, todayStr]
  );

  const previewImpact = useMemo(() => {
    const check = validateActivityInput({ activityType, trips, distanceKm, date });
    if (!check.valid) return null;
    return calculateActivityImpact(check.normalized, assumptions);
  }, [activityType, trips, distanceKm, date, assumptions]);

  const handleAddRecord = (event) => {
    event.preventDefault();
    const check = validateActivityInput({ activityType, trips, distanceKm, date });
    if (!check.valid) {
      setFormErrors(check.errors);
      return;
    }

    setFormErrors({});
    const newRecord = {
      id: `imp-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      ...check.normalized,
    };
    setRecords((prev) => [newRecord, ...prev]);
  };

  const handleDeleteRecord = (id) => {
    setRecords((prev) => prev.filter((item) => item.id !== id));
  };

  const handleClearAll = () => {
    setRecords([]);
  };

  const handleSaveAssumptions = (event) => {
    event.preventDefault();
    const check = validateAssumptionsInput(assumptionsDraft);
    if (!check.valid) {
      setAssumptionsErrors(check.errors);
      return;
    }
    setAssumptionsErrors({});
    setAssumptions(check.normalized);
    setAssumptionsDraft(check.normalized);
    setShowAssumptions(false);
  };

  const handleResetAssumptions = () => {
    setAssumptionsErrors({});
    setAssumptions({ ...DEFAULT_EMISSION_ASSUMPTIONS });
    setAssumptionsDraft({ ...DEFAULT_EMISSION_ASSUMPTIONS });
  };

  const displayedHistory =
    historyScope === "weekly" ? summary.weeklyRecords : summary.enrichedRecords;

  return (
    <div className="space-y-6">
      {/* Header & Honest Estimate Disclosure */}
      <section className="rounded-2xl border border-mist-200 bg-white p-5 shadow-xs">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-start gap-3.5">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-pine-700 text-white shadow-xs">
              <Leaf className="h-5 w-5" />
            </div>
            <div>
              <h2 className="font-display text-lg font-bold text-slate-900">
                Environmental Impact Tracker
              </h2>
              <p className="mt-1 text-xs leading-relaxed text-slate-600">
                Track public transport, carpooling, avoided private vehicle trips, and
                walking or cycling to see estimated urban CO₂ reductions saved locally in
                your browser.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setShowAssumptions((prev) => !prev)}
              className="inline-flex items-center gap-1.5 rounded-xl border border-mist-200 bg-mist-50 px-3 py-2 text-xs font-semibold text-slate-700 transition hover:bg-mist-100"
            >
              <Settings2 className="h-3.5 w-3.5 text-pine-700" />
              {showAssumptions ? "Hide Assumptions" : "Baseline & Assumptions"}
            </button>

            {onBackToDashboard && (
              <button
                type="button"
                onClick={onBackToDashboard}
                className="rounded-xl border border-mist-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 transition hover:bg-mist-50"
              >
                Back to Dashboard
              </button>
            )}
          </div>
        </div>

        <div className="mt-4 flex items-start gap-2.5 rounded-xl border border-mist-200 bg-mist-50/80 px-3.5 py-2.5 text-xs text-slate-700">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-pine-700" />
          <p>
            <span className="font-semibold text-slate-900">Estimate Disclosure: </span>
            All CO₂ figures shown here are <strong>modeled estimates</strong> based on
            user-logged distances and configurable per-km emission factors compared against a{" "}
            <strong>
              {assumptions.baselineCarKgPerKm} kg CO₂e/km single-occupant urban car
              baseline
            </strong>
            —not directly measured emissions reductions.
          </p>
        </div>
      </section>

      {/* Configurable Assumptions & Baseline Panel */}
      {showAssumptions && (
        <section className="rounded-2xl border border-mist-200 bg-white p-5 shadow-xs">
          <div className="flex flex-col gap-2 border-b border-mist-100 pb-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h3 className="font-display text-sm font-bold text-slate-900">
                Configurable Emission Factors &amp; Baseline Methodology
              </h3>
              <p className="text-xs text-slate-500">
                Savings = (Car Baseline − Mode Factor) × Trips × Distance per Trip. Walking,
                cycling, and avoided car trips use 0 kg CO₂e/km operational tailpipe emissions.
              </p>
            </div>
            <button
              type="button"
              onClick={handleResetAssumptions}
              className="inline-flex items-center gap-1 self-start rounded-xl border border-mist-200 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-mist-50"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Reset Defaults
            </button>
          </div>

          <form onSubmit={handleSaveAssumptions} className="mt-4 grid gap-4 sm:grid-cols-3">
            <div>
              <label className="block text-xs font-medium text-slate-700">
                Baseline Private Car (kg CO₂e / km)
              </label>
              <input
                type="number"
                step="0.001"
                min="0.01"
                max="1.0"
                value={assumptionsDraft.baselineCarKgPerKm}
                onChange={(e) =>
                  setAssumptionsDraft((prev) => ({
                    ...prev,
                    baselineCarKgPerKm: e.target.value,
                  }))
                }
                className="mt-1 w-full rounded-xl border border-mist-200 px-3 py-2 text-sm focus:border-pine-600 focus:outline-none"
              />
              {assumptionsErrors.baselineCarKgPerKm && (
                <p className="mt-1 text-[11px] text-rose-700">
                  {assumptionsErrors.baselineCarKgPerKm}
                </p>
              )}
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700">
                Public Transport (kg CO₂e / passenger-km)
              </label>
              <input
                type="number"
                step="0.001"
                min="0"
                max="1.0"
                value={assumptionsDraft.publicTransportKgPerKm}
                onChange={(e) =>
                  setAssumptionsDraft((prev) => ({
                    ...prev,
                    publicTransportKgPerKm: e.target.value,
                  }))
                }
                className="mt-1 w-full rounded-xl border border-mist-200 px-3 py-2 text-sm focus:border-pine-600 focus:outline-none"
              />
              {assumptionsErrors.publicTransportKgPerKm && (
                <p className="mt-1 text-[11px] text-rose-700">
                  {assumptionsErrors.publicTransportKgPerKm}
                </p>
              )}
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700">
                Average Carpool Occupancy (passengers)
              </label>
              <input
                type="number"
                min="2"
                max="8"
                step="1"
                value={assumptionsDraft.carpoolPassengers}
                onChange={(e) =>
                  setAssumptionsDraft((prev) => ({
                    ...prev,
                    carpoolPassengers: Number(e.target.value),
                  }))
                }
                className="mt-1 w-full rounded-xl border border-mist-200 px-3 py-2 text-sm focus:border-pine-600 focus:outline-none"
              />
              {assumptionsErrors.carpoolPassengers && (
                <p className="mt-1 text-[11px] text-rose-700">
                  {assumptionsErrors.carpoolPassengers}
                </p>
              )}
            </div>

            <div className="flex justify-end gap-2 sm:col-span-3">
              <button
                type="submit"
                className="rounded-xl bg-pine-700 px-4 py-2 text-xs font-semibold text-white hover:bg-pine-800"
              >
                Apply Assumptions
              </button>
            </div>
          </form>
        </section>
      )}

      {/* Impact Dashboard KPI Cards */}
      <section aria-label="Impact Summary" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-2xl border border-mist-200 bg-white p-4 shadow-xs">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Estimated CO₂ Avoided
          </p>
          <p className="mt-1.5 font-display text-3xl font-bold text-pine-800">
            {summary.totalCo2AvoidedKg} <span className="text-base font-semibold">kg</span>
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Est. {summary.weeklyCo2AvoidedKg} kg (7d) · {summary.monthlyCo2AvoidedKg} kg (30d)
          </p>
        </div>

        <div className="rounded-2xl border border-mist-200 bg-white p-4 shadow-xs">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Total Sustainable Trips
          </p>
          <p className="mt-1.5 font-display text-3xl font-bold text-slate-900">
            {summary.totalTrips}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {summary.weeklyTrips} this week · {summary.monthlyTrips} in 30 days
          </p>
        </div>

        <div className="rounded-2xl border border-mist-200 bg-white p-4 shadow-xs">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Sustainable Distance
          </p>
          <p className="mt-1.5 font-display text-3xl font-bold text-slate-900">
            {summary.totalDistanceKm} <span className="text-base font-semibold">km</span>
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {summary.weeklyDistanceKm} km (7d) · {summary.monthlyDistanceKm} km (30d)
          </p>
        </div>

        <div className="rounded-2xl border border-mist-200 bg-white p-4 shadow-xs">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Comparison Baseline
          </p>
          <p className="mt-1.5 font-display text-2xl font-bold text-slate-900">
            {assumptions.baselineCarKgPerKm}{" "}
            <span className="text-xs font-semibold text-slate-600">kg CO₂e/km</span>
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Transit: {assumptions.publicTransportKgPerKm} kg/km · Carpool:{" "}
            {assumptions.carpoolPassengers} riders
          </p>
        </div>
      </section>

      {/* Activity Logger Form + Charts */}
      <div className="grid gap-6 lg:grid-cols-12">
        {/* Log Activity Form */}
        <section className="rounded-2xl border border-mist-200 bg-white p-5 shadow-xs lg:col-span-5">
          <div className="flex items-center gap-2 border-b border-mist-100 pb-3">
            <PlusCircle className="h-4 w-4 text-pine-700" />
            <h3 className="font-display text-base font-bold text-slate-900">
              Log Sustainable Activity
            </h3>
          </div>

          <form onSubmit={handleAddRecord} className="mt-4 space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-700">
                Activity Type
              </label>
              <select
                value={activityType}
                onChange={(e) => setActivityType(e.target.value)}
                className="mt-1 w-full rounded-xl border border-mist-200 bg-white px-3 py-2 text-sm focus:border-pine-600 focus:outline-none"
              >
                {ACTIVITY_TYPES.map((type) => (
                  <option key={type.id} value={type.id}>
                    {type.label}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-[11px] text-slate-500">
                {ACTIVITY_TYPES.find((t) => t.id === activityType)?.description}
              </p>
              {formErrors.activityType && (
                <p className="mt-1 text-xs text-rose-700">{formErrors.activityType}</p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-700">
                  Number of Trips
                </label>
                <input
                  type="number"
                  min={1}
                  max={50}
                  step={1}
                  value={trips}
                  onChange={(e) => setTrips(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-mist-200 px-3 py-2 text-sm focus:border-pine-600 focus:outline-none"
                />
                {formErrors.trips && (
                  <p className="mt-1 text-xs text-rose-700">{formErrors.trips}</p>
                )}
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700">
                  Distance per Trip (km)
                </label>
                <input
                  type="number"
                  min={0.1}
                  max={1000}
                  step="0.1"
                  value={distanceKm}
                  onChange={(e) => setDistanceKm(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-mist-200 px-3 py-2 text-sm focus:border-pine-600 focus:outline-none"
                />
                {formErrors.distanceKm && (
                  <p className="mt-1 text-xs text-rose-700">{formErrors.distanceKm}</p>
                )}
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700">Date</label>
              <input
                type="date"
                value={date}
                max={todayStr}
                onChange={(e) => setDate(e.target.value)}
                className="mt-1 w-full rounded-xl border border-mist-200 px-3 py-2 text-sm focus:border-pine-600 focus:outline-none"
              />
              {formErrors.date && (
                <p className="mt-1 text-xs text-rose-700">{formErrors.date}</p>
              )}
            </div>

            {previewImpact && (
              <div className="rounded-xl border border-pine-600/15 bg-pine-50/70 px-3.5 py-2.5 text-xs text-slate-700">
                <span className="font-semibold text-pine-900">Estimated Savings Preview: </span>
                {previewImpact.totalDistanceKm} km total ·{" "}
                <strong>~{previewImpact.co2AvoidedKg} kg CO₂e</strong> avoided vs car
                baseline
              </div>
            )}

            <button
              type="submit"
              className="w-full rounded-xl bg-pine-700 px-4 py-2.5 text-sm font-semibold text-white shadow-xs transition hover:bg-pine-800"
            >
              Add Activity Record
            </button>
          </form>
        </section>

        {/* Charts Panel */}
        <section className="space-y-6 lg:col-span-7">
          {/* Weekly Trend Chart */}
          <div className="rounded-2xl border border-mist-200 bg-white p-5 shadow-xs">
            <div className="mb-3 flex items-center justify-between gap-2">
              <div>
                <h3 className="text-sm font-semibold text-slate-900">
                  Weekly Estimated CO₂ Avoided (Last 7 Days)
                </h3>
                <p className="text-xs text-slate-500">
                  Daily estimated kg CO₂e avoided ({summary.weekStart} to {summary.referenceDate})
                </p>
              </div>
              <span className="rounded-full bg-mist-100 px-2.5 py-0.5 text-[11px] font-medium text-slate-600">
                Estimate · kg CO₂e
              </span>
            </div>

            {summary.weeklyTrips === 0 ? (
              <div className="flex h-48 items-center justify-center rounded-xl border border-dashed border-mist-200 bg-mist-50/60 px-4 text-center text-xs text-slate-500">
                Log a sustainable trip from the past 7 days to populate your weekly CO₂ chart.
              </div>
            ) : (
              <div className="h-48 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={summary.weeklySeries}
                    margin={{ top: 8, right: 8, left: -18, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#E2EBE6" />
                    <XAxis
                      dataKey="shortDate"
                      tick={{ fontSize: 11, fill: "#64748B" }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <YAxis
                      tick={{ fontSize: 11, fill: "#64748B" }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <Tooltip content={<ImpactTooltip />} />
                    <Bar
                      dataKey="co2AvoidedKg"
                      name="Est. CO₂ Avoided (kg)"
                      fill="#0F766E"
                      radius={[6, 6, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          {/* Mode Breakdown Chart */}
          <div className="rounded-2xl border border-mist-200 bg-white p-5 shadow-xs">
            <div className="mb-3 flex items-center justify-between gap-2">
              <div>
                <h3 className="text-sm font-semibold text-slate-900">
                  Estimated Savings by Activity Type
                </h3>
                <p className="text-xs text-slate-500">
                  Cumulative estimated kg CO₂e avoided across sustainable travel choices
                </p>
              </div>
            </div>

            {summary.totalTrips === 0 ? (
              <div className="flex h-44 items-center justify-center rounded-xl border border-dashed border-mist-200 bg-mist-50/60 px-4 text-center text-xs text-slate-500">
                No activity breakdown yet. Add trips to compare public transit, carpooling,
                avoided car trips, and active travel.
              </div>
            ) : (
              <div className="h-44 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={summary.byActivityType}
                    margin={{ top: 8, right: 8, left: -18, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#E2EBE6" />
                    <XAxis
                      dataKey="shortLabel"
                      tick={{ fontSize: 11, fill: "#64748B" }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <YAxis
                      tick={{ fontSize: 11, fill: "#64748B" }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <Tooltip content={<ImpactTooltip />} />
                    <Bar
                      dataKey="co2AvoidedKg"
                      name="Est. CO₂ Avoided (kg)"
                      fill="#0D9488"
                      radius={[6, 6, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </section>
      </div>

      {/* Weekly Activity History */}
      <section className="rounded-2xl border border-mist-200 bg-white p-5 shadow-xs">
        <div className="flex flex-col gap-3 border-b border-mist-100 pb-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <Route className="h-4 w-4 text-pine-700" />
            <div>
              <h3 className="font-display text-base font-bold text-slate-900">
                {historyScope === "weekly" ? "Weekly Activity History" : "All Activity Records"}
              </h3>
              <p className="text-xs text-slate-500">
                Stored locally in browser localStorage. Delete individual entries anytime.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex rounded-xl border border-mist-200 bg-mist-50 p-0.5 text-xs">
              <button
                type="button"
                onClick={() => setHistoryScope("weekly")}
                className={`rounded-lg px-3 py-1 font-semibold transition ${
                  historyScope === "weekly"
                    ? "bg-white text-pine-900 shadow-xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Last 7 Days ({summary.weeklyRecords.length})
              </button>
              <button
                type="button"
                onClick={() => setHistoryScope("all")}
                className={`rounded-lg px-3 py-1 font-semibold transition ${
                  historyScope === "all"
                    ? "bg-white text-pine-900 shadow-xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                All ({summary.enrichedRecords.length})
              </button>
            </div>

            {records.length > 0 && (
              <button
                type="button"
                onClick={handleClearAll}
                className="inline-flex items-center gap-1 rounded-xl border border-mist-200 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-mist-50"
              >
                <Trash2 className="h-3.5 w-3.5" />
                Clear All
              </button>
            )}
          </div>
        </div>

        {displayedHistory.length === 0 ? (
          <div className="mt-4">
            <EmptyState
              icon={Calendar}
              title={
                historyScope === "weekly"
                  ? "No sustainable trips logged in the last 7 days"
                  : "No sustainable trips logged yet"
              }
              description="Record your first public transport, carpool, avoided vehicle, or walking/cycling trip above to estimate emissions avoided."
            />
          </div>
        ) : (
          <div className="mt-4 divide-y divide-mist-100">
            {displayedHistory.map((item) => {
              const typeObj = ACTIVITY_TYPES.find((t) => t.id === item.activityType);
              const meta = ACTIVITY_META[item.activityType] || ACTIVITY_META.public_transport;
              const ItemIcon = meta.icon;

              return (
                <div
                  key={item.id}
                  className="flex flex-col gap-3 py-3 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="flex items-start gap-3">
                    <span
                      className={`mt-0.5 inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border ${meta.badge}`}
                    >
                      <ItemIcon className="h-4 w-4" />
                    </span>
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-semibold text-slate-900">
                          {typeObj?.label || item.activityType}
                        </span>
                        <span className="rounded-full bg-mist-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
                          {item.date}
                        </span>
                      </div>
                      <p className="mt-0.5 text-xs text-slate-600">
                        {item.trips} {item.trips === 1 ? "trip" : "trips"} × {item.distanceKm}{" "}
                        km = <strong>{item.totalDistanceKm} km</strong>
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center justify-between gap-4 sm:justify-end">
                    <div className="text-left sm:text-right">
                      <p className="text-sm font-bold text-pine-800">
                        ~{item.co2AvoidedKg} kg CO₂e
                      </p>
                      <p className="text-[11px] text-slate-500">Est. avoided</p>
                    </div>

                    <button
                      type="button"
                      onClick={() => handleDeleteRecord(item.id)}
                      aria-label={`Delete ${typeObj?.label || "activity"} record on ${item.date}`}
                      className="inline-flex items-center gap-1 rounded-xl border border-mist-200 px-2.5 py-1.5 text-xs font-medium text-slate-600 transition hover:border-rose-200 hover:bg-rose-50 hover:text-rose-700"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      Delete
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
