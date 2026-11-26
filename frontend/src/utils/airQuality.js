/**
 * Pure presentation helpers for AirWise air quality categories and timestamps.
 * Never fabricates readings when values are missing.
 */

export function getAqiAppearance(usAqi, dataStatus) {
  if (dataStatus === "unavailable" || usAqi === null || usAqi === undefined) {
    return {
      category: "Unavailable",
      badgeBg: "bg-slate-100 text-slate-700 border-slate-200",
      ringColor: "stroke-slate-300",
      accentText: "text-slate-500",
      panelTint: "from-slate-50 to-white",
      summary:
        "Live atmospheric telemetry could not be retrieved. No placeholder AQI values are shown.",
    };
  }

  if (usAqi <= 50) {
    return {
      category: "Good",
      badgeBg: "bg-emerald-50 text-emerald-800 border-emerald-200",
      ringColor: "stroke-emerald-500",
      accentText: "text-emerald-700",
      panelTint: "from-emerald-50/70 to-white",
      summary:
        "Air quality poses little or no risk. Ideal window for normal outdoor routines and cross-ventilation.",
    };
  }
  if (usAqi <= 100) {
    return {
      category: "Moderate",
      badgeBg: "bg-amber-50 text-amber-800 border-amber-200",
      ringColor: "stroke-amber-500",
      accentText: "text-amber-700",
      panelTint: "from-amber-50/70 to-white",
      summary:
        "Acceptable for most households, though unusually sensitive individuals should monitor symptoms.",
    };
  }
  if (usAqi <= 150) {
    return {
      category: "Unhealthy for Sensitive Groups",
      badgeBg: "bg-orange-50 text-orange-800 border-orange-200",
      ringColor: "stroke-orange-500",
      accentText: "text-orange-700",
      panelTint: "from-orange-50/70 to-white",
      summary:
        "Children, older adults, and people with respiratory conditions should limit prolonged outdoor exertion.",
    };
  }
  if (usAqi <= 200) {
    return {
      category: "Unhealthy",
      badgeBg: "bg-rose-50 text-rose-800 border-rose-200",
      ringColor: "stroke-rose-500",
      accentText: "text-rose-700",
      panelTint: "from-rose-50/70 to-white",
      summary:
        "Everyone may experience respiratory effects. Keep windows closed during peak smog hours and wear N95/KN95 masks outdoors.",
    };
  }
  if (usAqi <= 300) {
    return {
      category: "Very Unhealthy",
      badgeBg: "bg-purple-50 text-purple-800 border-purple-200",
      ringColor: "stroke-purple-600",
      accentText: "text-purple-700",
      panelTint: "from-purple-50/70 to-white",
      summary:
        "Health alert: elevated winter smog burden. Run HEPA filtration indoors and avoid outdoor exercise.",
    };
  }

  return {
    category: "Hazardous",
    badgeBg: "bg-red-100 text-red-900 border-red-300",
    ringColor: "stroke-red-700",
    accentText: "text-red-800",
    panelTint: "from-red-50/80 to-white",
    summary:
      "Emergency conditions. Minimize all outdoor exposure, seal drafts, and prioritize indoor air cleaning.",
  };
}

export function formatTimestamp(isoString) {
  if (!isoString) return "—";
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatHourLabel(isoString) {
  if (!isoString) return "";
  const parts = isoString.split("T");
  if (parts.length === 2) {
    return parts[1].slice(0, 5);
  }
  return isoString;
}
