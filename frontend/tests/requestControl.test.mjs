import test from "node:test";
import assert from "node:assert/strict";
import {
  InFlightRequestManager,
  RefreshCooldownTracker,
  classifyTelemetryFeedback,
} from "../src/utils/requestControl.js";

test("InFlightRequestManager deduplicates concurrent identical requests and caches valid GETs", async () => {
  let now = 1_000;
  let calls = 0;
  const manager = new InFlightRequestManager({
    defaultCacheTtlMs: 30_000,
    nowFn: () => now,
  });

  const slowFetcher = async () => {
    calls += 1;
    await new Promise((resolve) => setTimeout(resolve, 15));
    return { data_status: "live", us_aqi: 142 };
  };

  // Concurrent callers share one underlying fetch
  const [a, b, c] = await Promise.all([
    manager.execute("/api/v1/air-quality?location_id=kolkata-in", slowFetcher),
    manager.execute("/api/v1/air-quality?location_id=kolkata-in", slowFetcher),
    manager.execute("/api/v1/air-quality?location_id=kolkata-in", slowFetcher),
  ]);
  assert.equal(calls, 1);
  assert.deepEqual(a, b);
  assert.deepEqual(b, c);

  // Subsequent non-bypassed call within TTL reuses cached response
  const d = await manager.execute(
    "/api/v1/air-quality?location_id=kolkata-in",
    slowFetcher
  );
  assert.equal(calls, 1);
  assert.equal(d.us_aqi, 142);

  // Explicit force refresh (bypassCache=true) triggers a new call
  const e = await manager.execute(
    "/api/v1/air-quality?location_id=kolkata-in",
    slowFetcher,
    { bypassCache: true }
  );
  assert.equal(calls, 2);
  assert.equal(e.us_aqi, 142);
});

test("InFlightRequestManager does not cache unavailable payloads", async () => {
  let calls = 0;
  const manager = new InFlightRequestManager({ defaultCacheTtlMs: 30_000 });
  const unavailableFetcher = async () => {
    calls += 1;
    return { data_status: "unavailable", rate_limited: true };
  };

  await manager.execute("/api/v1/air-quality?x=1", unavailableFetcher);
  await manager.execute("/api/v1/air-quality?x=1", unavailableFetcher);
  assert.equal(calls, 2);
});

test("RefreshCooldownTracker enforces default cooldown and honors server Retry-After", () => {
  let now = 10_000;
  const tracker = new RefreshCooldownTracker({
    defaultCooldownMs: 15_000,
    nowFn: () => now,
  });

  assert.equal(tracker.canRefresh(), true);
  assert.equal(tracker.getRemainingSeconds(), 0);

  const rem1 = tracker.recordAttempt();
  assert.equal(rem1, 15);
  assert.equal(tracker.canRefresh(), false);

  now += 10_000;
  assert.equal(tracker.getRemainingSeconds(), 5);
  assert.equal(tracker.canRefresh(), false);

  now += 5_000;
  assert.equal(tracker.canRefresh(), true);
  assert.equal(tracker.getRemainingSeconds(), 0);

  // Server Retry-After=45 extends cooldown past default 15s
  const rem2 = tracker.recordAttempt({ retryAfterSeconds: 45 });
  assert.equal(rem2, 45);
  assert.equal(tracker.canRefresh(), false);
});

test("classifyTelemetryFeedback separates rate-limited, backend unavailable, no cache, stale, and fresh states", () => {
  const backendDown = classifyTelemetryFeedback({
    airQuality: null,
    error: { message: "Failed to fetch" },
  });
  assert.equal(backendDown.kind, "backend_unavailable");

  const rateLimitedNoCache = classifyTelemetryFeedback({
    airQuality: {
      data_status: "unavailable",
      rate_limited: true,
      retry_after_seconds: 60,
      error_detail: "HTTP 429",
    },
    error: null,
  });
  assert.equal(rateLimitedNoCache.kind, "rate_limited");
  assert.match(rateLimitedNoCache.title, /Rate Limited/i);

  const rateLimitedWithCache = classifyTelemetryFeedback({
    airQuality: {
      data_status: "cached",
      is_stale: true,
      rate_limited: true,
      retry_after_seconds: 30,
      api_warning: "HTTP 429",
    },
    error: null,
  });
  assert.equal(rateLimitedWithCache.kind, "rate_limited");
  assert.match(rateLimitedWithCache.title, /Stale Cached/i);

  const noCache = classifyTelemetryFeedback({
    airQuality: { data_status: "unavailable", rate_limited: false, error_detail: "Down" },
    error: null,
  });
  assert.equal(noCache.kind, "no_cached_data");

  const stale = classifyTelemetryFeedback({
    airQuality: { data_status: "cached", is_stale: true, stale_reason: "12m old" },
    error: null,
  });
  assert.equal(stale.kind, "stale_cached");

  const fresh = classifyTelemetryFeedback({
    airQuality: { data_status: "live", is_stale: false },
    error: null,
  });
  assert.equal(fresh.kind, "fresh_live");
});
