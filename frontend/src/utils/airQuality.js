/**
 * Pure presentation helpers for AirWise air quality categories and timestamps.
 * Never fabricates readings when values are missing.
 */

export function getAqiAppearance(usAqi, dataStatus) {
  if (dataStatus === "unavailable" || usAqi === null || usAqi === undefined) {
    return {
      category: "Unavailable",
      badgeBg: "bg-slate-100 text-slate-700 border-slate-200",
      panelTint: "from-slate-50 to-white",
      summary:
        "Live atmospheric telemetry could not be retrieved. No placeholder AQI values are shown.",
    };
  }

  if (usAqi <= 50) {
    return {
      category: "Good",
      badgeBg: "bg-emerald-50 text-emerald-800 border-emerald-200",
      panelTint: "from-emerald-50/70 to-white",
      summary:
        "Air quality poses little or no risk. Ideal window for normal outdoor routines and cross-ventilation.",
    };
  }
  if (usAqi <= 100) {
    return {
      category: "Moderate",
      badgeBg: "bg-amber-50 text-amber-800 border-amber-200",
      panelTint: "from-amber-50/70 to-white",
      summary:
        "Acceptable for most households, though unusually sensitive individuals should monitor symptoms.",
    };
  }
  if (usAqi <= 150) {
    return {
      category: "Unhealthy for Sensitive Groups",
      badgeBg: "bg-orange-50 text-orange-800 border-orange-200",
      panelTint: "from-orange-50/70 to-white",
      summary:
        "Children, older adults, and people with respiratory conditions should limit prolonged outdoor exertion.",
    };
  }
  if (usAqi <= 200) {
    return {
      category: "Unhealthy",
      badgeBg: "bg-rose-50 text-rose-800 border-rose-200",
      panelTint: "from-rose-50/70 to-white",
      summary:
        "Everyone may experience respiratory effects. Keep windows closed during peak smog hours and wear N95/KN95 masks outdoors.",
    };
  }
  if (usAqi <= 300) {
    return {
      category: "Very Unhealthy",
      badgeBg: "bg-purple-50 text-purple-800 border-purple-200",
      panelTint: "from-purple-50/70 to-white",
      summary:
        "Health alert: elevated winter smog burden. Run HEPA filtration indoors and avoid outdoor exercise.",
    };
  }

  return {
    category: "Hazardous",
    badgeBg: "bg-red-100 text-red-900 border-red-300",
    panelTint: "from-red-50/80 to-white",
    summary:
      "Emergency conditions. Minimize all outdoor exposure, seal drafts, and prioritize indoor air cleaning.",
  };
}

export function getCpcbAqiAppearance(cpcbAqi, status) {
  if (status === "unavailable" || cpcbAqi === null || cpcbAqi === undefined) {
    return {
      category: "Unavailable",
      badgeBg: "bg-slate-100 text-slate-700 border-slate-200",
      panelTint: "from-slate-50 to-white",
    };
  }

  if (cpcbAqi <= 50) {
    return {
      category: "Good",
      badgeBg: "bg-emerald-50 text-emerald-800 border-emerald-200",
      panelTint: "from-emerald-50/70 to-white",
    };
  }
  if (cpcbAqi <= 100) {
    return {
      category: "Satisfactory",
      badgeBg: "bg-lime-50 text-lime-800 border-lime-200",
      panelTint: "from-lime-50/70 to-white",
    };
  }
  if (cpcbAqi <= 200) {
    return {
      category: "Moderate",
      badgeBg: "bg-amber-50 text-amber-800 border-amber-200",
      panelTint: "from-amber-50/70 to-white",
    };
  }
  if (cpcbAqi <= 300) {
    return {
      category: "Poor",
      badgeBg: "bg-orange-50 text-orange-800 border-orange-200",
      panelTint: "from-orange-50/70 to-white",
    };
  }
  if (cpcbAqi <= 400) {
    return {
      category: "Very Poor",
      badgeBg: "bg-rose-50 text-rose-800 border-rose-200",
      panelTint: "from-rose-50/70 to-white",
    };
  }

  return {
    category: "Severe",
    badgeBg: "bg-red-100 text-red-900 border-red-300",
    panelTint: "from-red-50/80 to-white",
  };
}

export function getValueKindMeta(valueKind) {
  if (valueKind === "observed") {
    return {
      label: "Observed",
      classes: "bg-emerald-50 text-emerald-800 border-emerald-200",
    };
  }
  if (valueKind === "forecast") {
    return {
      label: "Forecast",
      classes: "bg-indigo-50 text-indigo-800 border-indigo-200",
    };
  }
  return {
    label: "Estimated",
    classes: "bg-amber-50 text-amber-800 border-amber-200",
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

export function formatObservationTime(isoString) {
  if (!isoString) return "—";
  const parts = String(isoString).split("T");
  if (parts.length === 2) {
    return `${parts[0]} ${parts[1].slice(0, 5)}`;
  }
  return String(isoString);
}

export function formatHourLabel(isoString) {
  if (!isoString) return "";
  const parts = isoString.split("T");
  if (parts.length === 2) {
    return parts[1].slice(0, 5);
  }
  return isoString;
}
