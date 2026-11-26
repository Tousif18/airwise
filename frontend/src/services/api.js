import { InFlightRequestManager } from "../utils/requestControl";

const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(
    /\/+$/,
    ""
  );

const FAMILY_PROFILE_STORAGE_KEY = "airwise_family_profile_v1";
const HOME_ENVIRONMENT_STORAGE_KEY = "airwise_indoor_environment_v1";

const getRequestManager = new InFlightRequestManager({
  defaultCacheTtlMs: 60_000,
});

async function requestJson(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
      ...options,
    });
  } catch (networkErr) {
    const err = new Error(
      "Unable to reach the AirWise backend server. Please try again shortly."
    );
    err.isNetworkError = true;
    err.cause = networkErr;
    throw err;
  }

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const errBody = await response.json();
      if (errBody?.detail) {
        message =
          typeof errBody.detail === "string"
            ? errBody.detail
            : JSON.stringify(errBody.detail);
      }
    } catch {
      // Keep status message when body is not JSON
    }
    const err = new Error(message);
    err.status = response.status;
    throw err;
  }

  return response.json();
}

function cachedGet(path, { bypassCache = false, cacheTtlMs = 60_000, signal } = {}) {
  return getRequestManager.execute(
    path,
    () => requestJson(path, signal ? { signal } : {}),
    { bypassCache, cacheTtlMs }
  );
}

export function loadLocalFamilyProfile() {
  try {
    const raw = window.localStorage.getItem(FAMILY_PROFILE_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
}

export function saveLocalFamilyProfile(profile) {
  try {
    if (profile && typeof profile === "object") {
      window.localStorage.setItem(FAMILY_PROFILE_STORAGE_KEY, JSON.stringify(profile));
    }
  } catch {
    // Ignore storage quota or private-mode errors
  }
}

export function loadLocalHomeEnvironment() {
  try {
    const raw = window.localStorage.getItem(HOME_ENVIRONMENT_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
}

export function saveLocalHomeEnvironment(profile) {
  try {
    if (profile && typeof profile === "object") {
      window.localStorage.setItem(HOME_ENVIRONMENT_STORAGE_KEY, JSON.stringify(profile));
    }
  } catch {
    // Ignore storage errors
  }
}

export async function fetchHealth() {
  return cachedGet("/api/v1/health", { cacheTtlMs: 30_000 });
}

export async function fetchAssistantHealth() {
  return cachedGet("/api/v1/assistant/health", { cacheTtlMs: 30_000 });
}

export async function fetchAssistantStatus() {
  return fetchAssistantHealth();
}

export async function fetchPresetLocations() {
  return cachedGet("/api/v1/locations/presets", { cacheTtlMs: 600_000 });
}

export async function searchLocations(query) {
  const params = new URLSearchParams({ q: query.trim() });
  return cachedGet(`/api/v1/locations/search?${params.toString()}`, {
    cacheTtlMs: 300_000,
  });
}

export async function fetchAirQuality(location, { forceRefresh = false } = {}) {
  const params = new URLSearchParams();
  if (location?.latitude != null && location?.longitude != null) {
    params.set("latitude", String(location.latitude));
    params.set("longitude", String(location.longitude));
    if (location.id) params.set("location_id", location.id);
    if (location.name) params.set("name", location.name);
    if (location.region) params.set("region", location.region);
    if (location.country) params.set("country", location.country);
    if (location.timezone) params.set("timezone", location.timezone);
  } else if (location?.id) {
    params.set("location_id", location.id);
  }
  if (forceRefresh) {
    params.set("force_refresh", "true");
  }
  return cachedGet(`/api/v1/air-quality?${params.toString()}`, {
    bypassCache: forceRefresh,
    cacheTtlMs: 60_000,
  });
}

export async function fetchFamilyProfile() {
  return cachedGet("/api/v1/family/profile", { cacheTtlMs: 10_000 });
}

export async function saveFamilyProfile(profile) {
  const saved = await requestJson("/api/v1/family/profile", {
    method: "PUT",
    body: JSON.stringify(profile),
  });
  saveLocalFamilyProfile(saved);
  return saved;
}

export async function postAssistantChat(payload) {
  return requestJson("/api/v1/assistant/chat", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function postAssistantRecommendations(payload) {
  return requestJson("/api/v1/assistant/recommendations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function postIndoorRecommendations(payload) {
  return requestJson("/api/v1/indoor/recommendations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export { API_BASE_URL, FAMILY_PROFILE_STORAGE_KEY, HOME_ENVIRONMENT_STORAGE_KEY };
