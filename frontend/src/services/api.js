const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(
    /\/+$/,
    ""
  );

async function requestJson(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

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
    throw new Error(message);
  }

  return response.json();
}

export async function fetchHealth() {
  return requestJson("/api/v1/health");
}

export async function fetchAssistantStatus() {
  return requestJson("/api/v1/assistant/status");
}

export async function fetchPresetLocations() {
  return requestJson("/api/v1/locations/presets");
}

export async function searchLocations(query) {
  const params = new URLSearchParams({ q: query });
  return requestJson(`/api/v1/locations/search?${params.toString()}`);
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
  return requestJson(`/api/v1/air-quality?${params.toString()}`);
}

export async function fetchFamilyProfile() {
  return requestJson("/api/v1/family-profile");
}

export async function saveFamilyProfile(profile) {
  return requestJson("/api/v1/family-profile", {
    method: "PUT",
    body: JSON.stringify(profile),
  });
}

export { API_BASE_URL };
