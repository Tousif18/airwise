import test from "node:test";
import assert from "node:assert/strict";
import {
  DEFAULT_EMISSION_ASSUMPTIONS,
  calculateActivityImpact,
  summarizeImpact,
  validateActivityInput,
  validateAssumptionsInput,
} from "../src/utils/emissions.js";

test("calculateActivityImpact computes transparent savings against baseline", () => {
  // 2 trips x 10 km = 20 km
  // Public transport: 20 * (0.171 - 0.045) = 2.52 kg CO2e avoided
  const transit = calculateActivityImpact(
    { activityType: "public_transport", trips: 2, distanceKm: 10, date: "2026-11-26" },
    DEFAULT_EMISSION_ASSUMPTIONS
  );
  assert.equal(transit.totalDistanceKm, 20);
  assert.equal(transit.co2AvoidedKg, 2.52);

  // Carpooling (3 passengers): 20 * (0.171 - 0.171/3) = 2.28 kg CO2e avoided
  const carpool = calculateActivityImpact(
    { activityType: "carpooling", trips: 2, distanceKm: 10, date: "2026-11-26" },
    DEFAULT_EMISSION_ASSUMPTIONS
  );
  assert.equal(carpool.co2AvoidedKg, 2.28);

  // Walking/cycling & private vehicle avoided: full baseline saved = 20 * 0.171 = 3.42 kg
  const walk = calculateActivityImpact(
    { activityType: "walking_cycling", trips: 2, distanceKm: 10, date: "2026-11-26" },
    DEFAULT_EMISSION_ASSUMPTIONS
  );
  assert.equal(walk.co2AvoidedKg, 3.42);

  const avoided = calculateActivityImpact(
    { activityType: "vehicle_avoided", trips: 2, distanceKm: 10, date: "2026-11-26" },
    DEFAULT_EMISSION_ASSUMPTIONS
  );
  assert.equal(avoided.co2AvoidedKg, 3.42);
});

test("calculateActivityImpact responds to custom configurable assumptions", () => {
  const custom = {
    baselineCarKgPerKm: 0.2,
    publicTransportKgPerKm: 0.05,
    carpoolPassengers: 4,
  };
  const transit = calculateActivityImpact(
    { activityType: "public_transport", trips: 1, distanceKm: 10, date: "2026-11-26" },
    custom
  );
  assert.equal(transit.co2AvoidedKg, 1.5);

  const carpool = calculateActivityImpact(
    { activityType: "carpooling", trips: 1, distanceKm: 10, date: "2026-11-26" },
    custom
  );
  // 10 * (0.2 - 0.05) = 1.5
  assert.equal(carpool.co2AvoidedKg, 1.5);
});

test("validateActivityInput rejects invalid trips, distance, type, and date", () => {
  const invalid = validateActivityInput({
    activityType: "private_jet",
    trips: 0,
    distanceKm: -5,
    date: "2026-02-30",
  });
  assert.equal(invalid.valid, false);
  assert.ok(invalid.errors.activityType);
  assert.ok(invalid.errors.trips);
  assert.ok(invalid.errors.distanceKm);
  assert.ok(invalid.errors.date);

  const valid = validateActivityInput({
    activityType: "walking_cycling",
    trips: 3,
    distanceKm: 2.5,
    date: "2026-11-26",
  });
  assert.equal(valid.valid, true);
  assert.deepEqual(valid.errors, {});
});

test("validateAssumptionsInput enforces baseline >= transit and carpool >= 2", () => {
  const invalid = validateAssumptionsInput({
    baselineCarKgPerKm: 0.04,
    publicTransportKgPerKm: 0.08,
    carpoolPassengers: 1,
  });
  assert.equal(invalid.valid, false);
  assert.ok(invalid.errors.publicTransportKgPerKm);
  assert.ok(invalid.errors.carpoolPassengers);
});

test("summarizeImpact computes weekly, monthly, total metrics and handles empty states", () => {
  const empty = summarizeImpact([], DEFAULT_EMISSION_ASSUMPTIONS, "2026-11-27");
  assert.equal(empty.totalCo2AvoidedKg, 0);
  assert.equal(empty.totalTrips, 0);
  assert.equal(empty.weeklySeries.length, 7);
  assert.equal(empty.byActivityType.length, 4);

  const records = [
    { id: "1", activityType: "walking_cycling", trips: 2, distanceKm: 5, date: "2026-11-27" }, // inside 7d & 30d: 10km, 1.71kg
    { id: "2", activityType: "public_transport", trips: 1, distanceKm: 10, date: "2026-11-22" }, // inside 7d & 30d: 10km, 1.26kg
    { id: "3", activityType: "vehicle_avoided", trips: 1, distanceKm: 10, date: "2026-11-05" }, // inside 30d only: 10km, 1.71kg
    { id: "4", activityType: "carpooling", trips: 1, distanceKm: 10, date: "2026-10-01" }, // older than 30d: 10km, 1.14kg
  ];
  const summary = summarizeImpact(records, DEFAULT_EMISSION_ASSUMPTIONS, "2026-11-27");

  assert.equal(summary.weeklyTrips, 3);
  assert.equal(summary.weeklyDistanceKm, 20);
  assert.equal(summary.weeklyCo2AvoidedKg, 2.97);

  assert.equal(summary.monthlyTrips, 4);
  assert.equal(summary.monthlyDistanceKm, 30);
  assert.equal(summary.monthlyCo2AvoidedKg, 4.68);

  assert.equal(summary.totalTrips, 5);
  assert.equal(summary.totalDistanceKm, 40);
  assert.equal(summary.totalCo2AvoidedKg, 5.82);
  assert.equal(summary.weeklyRecords.length, 2);
});
