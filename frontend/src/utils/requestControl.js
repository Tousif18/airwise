/**
 * Pure request coalescing, short-lived GET cache, refresh cooldown,
 * and telemetry status classification helpers.
 */

export const DEFAULT_REFRESH_COOLDOWN_MS = 15_000;

export class InFlightRequestManager {
  constructor({ defaultCacheTtlMs = 0, nowFn = () => Date.now() } = {}) {
    this._inFlight = new Map();
    this._cache = new Map();
    this._defaultCacheTtlMs = Math.max(0, defaultCacheTtlMs);
    this._now = nowFn;
  }

  /**
   * Deduplicate concurrent identical requests and optionally reuse non-expired GET responses.
   */
  async execute(key, fetcher, { bypassCache = false, cacheTtlMs = this._defaultCacheTtlMs } = {}) {
    if (!bypassCache && cacheTtlMs > 0) {
      const cached = this._cache.get(key);
      if (cached && this._now() < cached.expiresAt) {
        return cached.value;
      }
    }

    if (this._inFlight.has(key)) {
      return this._inFlight.get(key);
    }

    const promise = Promise.resolve()
      .then(() => fetcher())
      .then((result) => {
        if (cacheTtlMs > 0 && result && result.data_status !== "unavailable") {
          this._cache.set(key, {
            value: result,
            expiresAt: this._now() + cacheTtlMs,
          });
        }
        return result;
      })
      .finally(() => {
        this._inFlight.delete(key);
      });

    this._inFlight.set(key, promise);
    return promise;
  }

  clear() {
    this._inFlight.clear();
    this._cache.clear();
  }
}

export class RefreshCooldownTracker {
  constructor({ defaultCooldownMs = DEFAULT_REFRESH_COOLDOWN_MS, nowFn = () => Date.now() } = {}) {
    this._defaultCooldownMs = Math.max(0, defaultCooldownMs);
    this._now = nowFn;
    this._cooldownUntil = 0;
  }

  canRefresh() {
    return this._now() >= this._cooldownUntil;
  }

  getRemainingSeconds() {
    const remainingMs = this._cooldownUntil - this._now();
    if (remainingMs <= 0) return 0;
    return Math.ceil(remainingMs / 1000);
  }

  recordAttempt({ retryAfterSeconds = null } = {}) {
    const requestedMs =
      typeof retryAfterSeconds === "number" && retryAfterSeconds > 0
        ? retryAfterSeconds * 1000
        : this._defaultCooldownMs;
    const durationMs = Math.max(this._defaultCooldownMs, requestedMs);
    this._cooldownUntil = this._now() + durationMs;
    return this.getRemainingSeconds();
  }

  reset() {
    this._cooldownUntil = 0;
  }
}

/**
 * Classify air-quality fetch outcome into one of five explicit user-facing states:
 * - "backend_unavailable"
 * - "rate_limited"
 * - "no_cached_data"
 * - "stale_cached"
 * - "fresh_live"
 */
export function classifyTelemetryFeedback({ airQuality, error }) {
  if (error && !airQuality) {
    return {
      kind: "backend_unavailable",
      title: "Backend Unavailable",
      message:
        error.message ||
        "Unable to reach the AirWise backend API. Readings remain unavailable until connection is restored.",
    };
  }

  if (airQuality?.rate_limited) {
    const waitHint = airQuality.retry_after_seconds
      ? ` Wait about ${airQuality.retry_after_seconds}s before refreshing.`
      : "";
    if (airQuality.data_status === "cached") {
      return {
        kind: "rate_limited",
        title: "Rate Limited by Open-Meteo — Showing Stale Cached Data",
        message: `${airQuality.api_warning || "Open-Meteo returned HTTP 429 Too Many Requests."}${waitHint}`,
      };
    }
    return {
      kind: "rate_limited",
      title: "Rate Limited by Open-Meteo — No Cached Data Available",
      message: `${airQuality.error_detail || "Open-Meteo returned HTTP 429 Too Many Requests and no prior cached telemetry exists."}${waitHint}`,
    };
  }

  if (error && airQuality) {
    return {
      kind: "backend_unavailable",
      title: "Backend Refresh Failed",
      message: error.message || "Could not refresh telemetry from the AirWise backend.",
    };
  }

  if (airQuality?.data_status === "unavailable") {
    return {
      kind: "no_cached_data",
      title: "No Cached Data Available",
      message:
        airQuality.error_detail ||
        airQuality.api_warning ||
        "Open-Meteo air quality telemetry is unavailable and no cached fallback exists.",
    };
  }

  if (airQuality?.data_status === "cached" && airQuality?.is_stale) {
    return {
      kind: "stale_cached",
      title: "Stale Cached Data Displayed",
      message:
        airQuality.stale_reason ||
        airQuality.api_warning ||
        "Displaying stale cached telemetry from an earlier fetch.",
    };
  }

  return {
    kind: "fresh_live",
    title: "Fresh Telemetry Active",
    message: "Showing verified Open-Meteo telemetry.",
  };
}
