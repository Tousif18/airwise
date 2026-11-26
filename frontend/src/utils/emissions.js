/**
 * Pure emission estimation utilities for AirWise Environmental Impact Tracker.
 *
 * All figures are transparent estimates relative to a configurable urban
 * single-occupant car baseline — never directly measured emissions reductions.
 */

export const IMPACT_RECORDS_STORAGE_KEY = "airwise_impact_records_v1";
export const EMISSION_ASSUMPTIONS_STORAGE_KEY = "airwise_emission_assumptions_v1";

export const ACTIVITY_TYPES = [
  {
    id: "public_transport",
    label: "Public Transport",
    shortLabel: "Transit",
    description: "Metro, urban bus, or suburban rail instead of a private car",
  },
  {
    id: "carpooling",
    label: "Carpooling",
    shortLabel: "Carpool",
    description: "Sharing a car ride with multiple passengers",
  },
  {
    id: "vehicle_avoided",
    label: "Private Vehicle Avoided",
    shortLabel: "Trip Avoided",
    description: "Errand combined, shifted remote, or private vehicle trip skipped",
  },
  {
    id: "walking_cycling",
    label: "Walking & Cycling",
    shortLabel: "Walk / Cycle",
    description: "Zero-tailpipe active travel replacing a motorized trip",
  },
];

export const VALID_ACTIVITY_IDS = new Set(ACTIVITY_TYPES.map((item) => item.id));

export const DEFAULT_EMISSION_ASSUMPTIONS = {
  baselineCarKgPerKm: 0.171,
  publicTransportKgPerKm: 0.045,
  carpoolPassengers: 3,
};

function roundTo(value, decimals = 2) {
  const factor = 10 ** decimals;
  return Math.round((value + Number.EPSILON) * factor) / factor;
}

export function isValidIsoDate(dateStr) {
  if (typeof dateStr !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
    return false;
  }
  const [y, m, d] = dateStr.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  return (
    dt.getUTCFullYear() === y &&
    dt.getUTCMonth() === m - 1 &&
    dt.getUTCDate() === d
  );
}

export function getTodayIsoDate(now = new Date()) {
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function shiftIsoDate(isoDate, deltaDays) {
  const [y, m, d] = isoDate.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d + deltaDays));
  const year = dt.getUTCFullYear();
  const month = String(dt.getUTCMonth() + 1).padStart(2, "0");
  const day = String(dt.getUTCDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function normalizeAssumptions(raw) {
  const candidate = raw && typeof raw === "object" ? raw : {};
  const baseline = Number(candidate.baselineCarKgPerKm);
  const transit = Number(candidate.publicTransportKgPerKm);
  const passengers = Number(candidate.carpoolPassengers);

  return {
    baselineCarKgPerKm:
      Number.isFinite(baseline) && baseline >= 0.01 && baseline <= 1.0
        ? roundTo(baseline, 3)
        : DEFAULT_EMISSION_ASSUMPTIONS.baselineCarKgPerKm,
    publicTransportKgPerKm:
      Number.isFinite(transit) && transit >= 0 && transit <= 1.0
        ? roundTo(transit, 3)
        : DEFAULT_EMISSION_ASSUMPTIONS.publicTransportKgPerKm,
    carpoolPassengers:
      Number.isFinite(passengers) && passengers >= 2 && passengers <= 8
        ? Math.round(passengers)
        : DEFAULT_EMISSION_ASSUMPTIONS.carpoolPassengers,
  };
}

export function validateAssumptionsInput(raw) {
  const errors = {};
  const baseline = Number(raw?.baselineCarKgPerKm);
  const transit = Number(raw?.publicTransportKgPerKm);
  const passengers = Number(raw?.carpoolPassengers);

  if (!Number.isFinite(baseline) || baseline < 0.01 || baseline > 1.0) {
    errors.baselineCarKgPerKm = "Baseline car factor must be between 0.01 and 1.0 kg CO₂e/km.";
  }
  if (!Number.isFinite(transit) || transit < 0 || transit > 1.0) {
    errors.publicTransportKgPerKm = "Public transport factor must be between 0 and 1.0 kg CO₂e/km.";
  } else if (Number.isFinite(baseline) && transit > baseline) {
    errors.publicTransportKgPerKm = "Public transport factor cannot exceed the car baseline for savings.";
  }
  if (!Number.isInteger(passengers) || passengers < 2 || passengers > 8) {
    errors.carpoolPassengers = "Carpool occupancy must be a whole number between 2 and 8.";
  }

  return {
    valid: Object.keys(errors).length === 0,
    errors,
    normalized: normalizeAssumptions(raw),
  };
}

export function validateActivityInput({ activityType, trips, distanceKm, date }) {
  const errors = {};

  if (!VALID_ACTIVITY_IDS.has(activityType)) {
    errors.activityType = "Select a valid sustainable activity type.";
  }

  const parsedTrips = Number(trips);
  if (!Number.isInteger(parsedTrips) || parsedTrips < 1 || parsedTrips > 50) {
    errors.trips = "Number of trips must be a whole number between 1 and 50.";
  }

  const parsedDistance = Number(distanceKm);
  if (!Number.isFinite(parsedDistance) || parsedDistance <= 0 || parsedDistance > 1000) {
    errors.distanceKm = "Approximate distance must be greater than 0 and up to 1000 km.";
  }

  if (!isValidIsoDate(date)) {
    errors.date = "Enter a valid date (YYYY-MM-DD).";
  }

  return {
    valid: Object.keys(errors).length === 0,
    errors,
    normalized: {
      activityType,
      trips: Number.isInteger(parsedTrips) ? parsedTrips : 1,
      distanceKm: Number.isFinite(parsedDistance) ? roundTo(parsedDistance, 2) : 0,
      date,
    },
  };
}

export function getActivityModeFactorKgPerKm(activityType, rawAssumptions = DEFAULT_EMISSION_ASSUMPTIONS) {
  const assumptions = normalizeAssumptions(rawAssumptions);
  switch (activityType) {
    case "public_transport":
      return assumptions.publicTransportKgPerKm;
    case "carpooling":
      return assumptions.baselineCarKgPerKm / assumptions.carpoolPassengers;
    case "vehicle_avoided":
    case "walking_cycling":
      return 0;
    default:
      return assumptions.baselineCarKgPerKm;
  }
}

export function calculateActivityImpact(record, rawAssumptions = DEFAULT_EMISSION_ASSUMPTIONS) {
  const assumptions = normalizeAssumptions(rawAssumptions);
  const trips = Math.max(0, Number(record?.trips) || 0);
  const distancePerTripKm = Math.max(0, Number(record?.distanceKm) || 0);
  const totalDistanceKm = roundTo(trips * distancePerTripKm, 2);

  if (!VALID_ACTIVITY_IDS.has(record?.activityType) || totalDistanceKm <= 0) {
    return {
      totalDistanceKm: 0,
      baselineKg: 0,
      modeKg: 0,
      co2AvoidedKg: 0,
    };
  }

  const baselineKg = totalDistanceKm * assumptions.baselineCarKgPerKm;
  const modeKg = totalDistanceKm * getActivityModeFactorKgPerKm(record.activityType, assumptions);
  const co2AvoidedKg = Math.max(0, baselineKg - modeKg);

  return {
    totalDistanceKm,
    baselineKg: roundTo(baselineKg, 3),
    modeKg: roundTo(modeKg, 3),
    co2AvoidedKg: roundTo(co2AvoidedKg, 3),
  };
}

export function summarizeImpact(
  records = [],
  rawAssumptions = DEFAULT_EMISSION_ASSUMPTIONS,
  referenceDate = getTodayIsoDate()
) {
  const assumptions = normalizeAssumptions(rawAssumptions);
  const safeRecords = Array.isArray(records) ? records : [];
  const weekStart = shiftIsoDate(referenceDate, -6);
  const monthStart = shiftIsoDate(referenceDate, -29);

  let totalCo2AvoidedKg = 0;
  let totalTrips = 0;
  let totalDistanceKm = 0;

  let weeklyCo2AvoidedKg = 0;
  let weeklyTrips = 0;
  let weeklyDistanceKm = 0;

  let monthlyCo2AvoidedKg = 0;
  let monthlyTrips = 0;
  let monthlyDistanceKm = 0;

  const byModeMap = Object.fromEntries(
    ACTIVITY_TYPES.map((type) => [
      type.id,
      {
        activityType: type.id,
        label: type.label,
        shortLabel: type.shortLabel,
        co2AvoidedKg: 0,
        trips: 0,
        distanceKm: 0,
      },
    ])
  );

  const weeklyBuckets = [];
  const weeklyBucketMap = {};
  for (let offset = -6; offset <= 0; offset += 1) {
    const dateKey = shiftIsoDate(referenceDate, offset);
    const bucket = {
      date: dateKey,
      shortDate: dateKey.slice(5),
      co2AvoidedKg: 0,
      trips: 0,
      distanceKm: 0,
    };
    weeklyBuckets.push(bucket);
    weeklyBucketMap[dateKey] = bucket;
  }

  const enrichedRecords = safeRecords
    .filter((rec) => rec && VALID_ACTIVITY_IDS.has(rec.activityType) && isValidIsoDate(rec.date))
    .map((rec) => {
      const impact = calculateActivityImpact(rec, assumptions);
      totalCo2AvoidedKg += impact.co2AvoidedKg;
      totalTrips += rec.trips;
      totalDistanceKm += impact.totalDistanceKm;

      if (rec.date >= weekStart && rec.date <= referenceDate) {
        weeklyCo2AvoidedKg += impact.co2AvoidedKg;
        weeklyTrips += rec.trips;
        weeklyDistanceKm += impact.totalDistanceKm;
        if (weeklyBucketMap[rec.date]) {
          weeklyBucketMap[rec.date].co2AvoidedKg = roundTo(
            weeklyBucketMap[rec.date].co2AvoidedKg + impact.co2AvoidedKg,
            2
          );
          weeklyBucketMap[rec.date].trips += rec.trips;
          weeklyBucketMap[rec.date].distanceKm = roundTo(
            weeklyBucketMap[rec.date].distanceKm + impact.totalDistanceKm,
            2
          );
        }
      }

      if (rec.date >= monthStart && rec.date <= referenceDate) {
        monthlyCo2AvoidedKg += impact.co2AvoidedKg;
        monthlyTrips += rec.trips;
        monthlyDistanceKm += impact.totalDistanceKm;
      }

      const modeEntry = byModeMap[rec.activityType];
      if (modeEntry) {
        modeEntry.co2AvoidedKg = roundTo(modeEntry.co2AvoidedKg + impact.co2AvoidedKg, 2);
        modeEntry.trips += rec.trips;
        modeEntry.distanceKm = roundTo(modeEntry.distanceKm + impact.totalDistanceKm, 2);
      }

      return {
        ...rec,
        ...impact,
      };
    })
    .sort((a, b) => (b.date > a.date ? 1 : b.date < a.date ? -1 : 0));

  const weeklyRecords = enrichedRecords.filter(
    (rec) => rec.date >= weekStart && rec.date <= referenceDate
  );

  return {
    totalCo2AvoidedKg: roundTo(totalCo2AvoidedKg, 2),
    totalTrips,
    totalDistanceKm: roundTo(totalDistanceKm, 1),
    weeklyCo2AvoidedKg: roundTo(weeklyCo2AvoidedKg, 2),
    weeklyTrips,
    weeklyDistanceKm: roundTo(weeklyDistanceKm, 1),
    monthlyCo2AvoidedKg: roundTo(monthlyCo2AvoidedKg, 2),
    monthlyTrips,
    monthlyDistanceKm: roundTo(monthlyDistanceKm, 1),
    weekStart,
    monthStart,
    referenceDate,
    weeklySeries: weeklyBuckets,
    byActivityType: ACTIVITY_TYPES.map((t) => byModeMap[t.id]),
    enrichedRecords,
    weeklyRecords,
  };
}

export function loadImpactRecords() {
  try {
    if (typeof window === "undefined" || !window.localStorage) return [];
    const raw = window.localStorage.getItem(IMPACT_RECORDS_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveImpactRecords(records) {
  try {
    if (typeof window !== "undefined" && window.localStorage && Array.isArray(records)) {
      window.localStorage.setItem(IMPACT_RECORDS_STORAGE_KEY, JSON.stringify(records));
    }
  } catch {
    // Ignore storage errors
  }
}

export function loadEmissionAssumptions() {
  try {
    if (typeof window === "undefined" || !window.localStorage) {
      return { ...DEFAULT_EMISSION_ASSUMPTIONS };
    }
    const raw = window.localStorage.getItem(EMISSION_ASSUMPTIONS_STORAGE_KEY);
    if (!raw) return { ...DEFAULT_EMISSION_ASSUMPTIONS };
    return normalizeAssumptions(JSON.parse(raw));
  } catch {
    return { ...DEFAULT_EMISSION_ASSUMPTIONS };
  }
}

export function saveEmissionAssumptions(assumptions) {
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      window.localStorage.setItem(
        EMISSION_ASSUMPTIONS_STORAGE_KEY,
        JSON.stringify(normalizeAssumptions(assumptions))
      );
    }
  } catch {
    // Ignore storage errors
  }
}
