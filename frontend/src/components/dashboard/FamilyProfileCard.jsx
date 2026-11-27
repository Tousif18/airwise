import { useEffect, useState } from "react";
import { Check, Edit3, HeartPulse, MapPin, Shield, Users } from "lucide-react";
import { LoadingCardSkeleton } from "../common/StateFeedback";

const SENSITIVITY_OPTIONS = [
  { value: "standard", label: "Standard" },
  { value: "moderate", label: "Moderate (Children / Older Adults)" },
  { value: "high", label: "High (Asthma / Respiratory Sensitivity)" },
];

const COMMUTE_OPTIONS = [
  { value: "public_transit", label: "Public Transit (Metro / Bus)" },
  { value: "walking", label: "Walking" },
  { value: "cycling", label: "Cycling" },
  { value: "two_wheeler", label: "Two-Wheeler / Scooter" },
  { value: "car_or_cab", label: "Car / Cab" },
  { value: "work_from_home", label: "Work / Study from Home" },
  { value: "mixed", label: "Mixed Commute" },
];

const VENTILATION_OPTIONS = [
  { value: "low_smog_windows", label: "Open only during low-smog hours" },
  { value: "natural_cross_ventilation", label: "Natural cross-ventilation" },
  { value: "sealed_with_purifier", label: "Keep sealed with indoor filtration" },
  { value: "minimal_opening", label: "Minimal window opening" },
];

function normalizeDraft(profile) {
  if (!profile) return null;
  const householdSize = Number(profile.household_size ?? profile.member_count ?? 4);
  const childrenCount = Number(
    profile.children_count ?? (profile.has_young_children ? 1 : 0)
  );
  const elderlyCount = Number(
    profile.elderly_count ?? (profile.has_older_adults ? 1 : 0)
  );
  return {
    city: profile.city || "Kolkata",
    location_id: profile.location_id || "kolkata-in",
    location_label: profile.location_label || profile.city || "Kolkata, West Bengal, India",
    household_size: householdSize,
    children_count: childrenCount,
    elderly_count: elderlyCount,
    has_respiratory_condition: Boolean(profile.has_respiratory_condition),
    respiratory_vulnerability: profile.respiratory_vulnerability || "",
    sensitivity_level: profile.sensitivity_level || "moderate",
    commute_method: profile.commute_method || "public_transit",
    daily_outdoor_commute:
      profile.daily_outdoor_commute !== undefined
        ? Boolean(profile.daily_outdoor_commute)
        : profile.commute_method !== "work_from_home",
    outdoor_activity_schedule: profile.outdoor_activity_schedule || "",
    ventilation_preference: profile.ventilation_preference || "low_smog_windows",
    has_air_purifier: Boolean(profile.has_air_purifier ?? profile.has_hepa_purifier),
    notes: profile.notes || "",
  };
}

function formatOptionLabel(options, value) {
  return options.find((opt) => opt.value === value)?.label || value;
}

export default function FamilyProfileCard({
  profile,
  loading,
  error,
  onSaveProfile,
  presets = [],
  compact = false,
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(() => normalizeDraft(profile));
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState(null);
  const [formError, setFormError] = useState(null);

  useEffect(() => {
    if (profile) {
      setDraft(normalizeDraft(profile));
    }
  }, [profile]);

  if (loading) {
    return <LoadingCardSkeleton lines={5} />;
  }

  if (!draft) {
    return (
      <section className="rounded-2xl border border-mist-200 bg-white p-5 shadow-xs">
        <p className="text-sm font-semibold text-slate-800">Family Profile</p>
        <p className="mt-1 text-xs text-slate-500">
          {error || "Household profile is currently unavailable."}
        </p>
      </section>
    );
  }

  const handleSave = async (event) => {
    event.preventDefault();
    setFormError(null);
    setSaveMessage(null);

    if (!draft.city.trim()) {
      setFormError("City is required.");
      return;
    }
    if (draft.children_count + draft.elderly_count > draft.household_size) {
      setFormError(
        "Number of children plus older adults cannot exceed total household size."
      );
      return;
    }

    setSaving(true);
    try {
      const payload = {
        ...draft,
        city: draft.city.trim(),
        location_label: (draft.location_label || draft.city).trim(),
        daily_outdoor_commute: draft.commute_method !== "work_from_home",
      };
      await onSaveProfile(payload);
      setEditing(false);
      setSaveMessage("Saved in this browser");
      setTimeout(() => setSaveMessage(null), 2500);
    } catch (err) {
      setFormError(err.message || "Failed to save profile");
    } finally {
      setSaving(false);
    }
  };

  const activeFlags = [
    draft.children_count > 0 &&
      `${draft.children_count} ${draft.children_count === 1 ? "Child" : "Children"}`,
    draft.elderly_count > 0 &&
      `${draft.elderly_count} ${draft.elderly_count === 1 ? "Older Adult" : "Older Adults"}`,
    draft.has_respiratory_condition && "Respiratory Sensitivity",
    draft.has_air_purifier ? "Air Purifier Available" : "No Air Purifier",
  ].filter(Boolean);

  return (
    <section
      aria-label="Family Profile"
      className="rounded-2xl border border-mist-200 bg-white p-5 shadow-xs"
    >
      <div className="flex flex-col gap-3 border-b border-mist-100 pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-pine-50 text-pine-700">
            <Users className="h-5 w-5" />
          </div>
          <div>
            <h2 className="font-display text-base font-bold text-slate-900">
              Family &amp; Household Profile
            </h2>
            <p className="text-xs text-slate-500">
              Saved only in this browser. Your profile is sent with your AI requests and is not stored on the AirWise server.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {saveMessage && (
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">
              <Check className="h-3.5 w-3.5" />
              {saveMessage}
            </span>
          )}
          <button
            type="button"
            onClick={() => {
              setFormError(null);
              setEditing((prev) => !prev);
            }}
            className="inline-flex items-center gap-1.5 rounded-xl border border-mist-200 bg-mist-50 px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:bg-mist-100"
          >
            <Edit3 className="h-3.5 w-3.5" />
            {editing ? "Cancel" : "Edit Profile"}
          </button>
        </div>
      </div>

      {(error || formError) && (
        <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          {formError || error}
        </p>
      )}

      {!editing ? (
        <div className={`mt-4 grid gap-3 ${compact ? "grid-cols-1" : "md:grid-cols-3"}`}>
          <div className="rounded-xl bg-mist-50 p-3.5">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Location &amp; Household
            </p>
            <div className="mt-1 flex items-center gap-1.5 text-sm font-semibold text-slate-900">
              <MapPin className="h-4 w-4 shrink-0 text-pine-700" />
              <span className="truncate">{draft.location_label || draft.city}</span>
            </div>
            <p className="mt-0.5 text-xs text-slate-600">
              {draft.household_size}{" "}
              {draft.household_size === 1 ? "member" : "members"} ·{" "}
              {formatOptionLabel(COMMUTE_OPTIONS, draft.commute_method)}
            </p>
          </div>

          <div className="rounded-xl bg-mist-50 p-3.5">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Sensitivity &amp; Home Air
            </p>
            <div className="mt-1 flex items-center gap-1.5 text-sm font-semibold capitalize text-slate-900">
              <HeartPulse className="h-4 w-4 shrink-0 text-pine-700" />
              <span>{draft.sensitivity_level} sensitivity</span>
            </div>
            <p className="mt-0.5 text-xs text-slate-600">
              Ventilation: {formatOptionLabel(VENTILATION_OPTIONS, draft.ventilation_preference)}
            </p>
          </div>

          <div className="rounded-xl bg-mist-50 p-3.5">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Vulnerability &amp; Protection
            </p>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {activeFlags.map((flag) => (
                <span
                  key={flag}
                  className="inline-flex items-center gap-1 rounded-full bg-white px-2.5 py-0.5 text-[11px] font-medium text-pine-900 ring-1 ring-mist-200"
                >
                  <Shield className="h-3 w-3 text-pine-700" />
                  {flag}
                </span>
              ))}
            </div>
            {draft.respiratory_vulnerability && (
              <p className="mt-1.5 text-[11px] text-slate-600">
                Note: {draft.respiratory_vulnerability}
              </p>
            )}
          </div>

          {(draft.outdoor_activity_schedule || draft.notes) && (
            <div
              className={`rounded-xl border border-mist-100 bg-white px-3.5 py-2.5 text-xs text-slate-600 ${
                compact ? "" : "md:col-span-3"
              }`}
            >
              {draft.outdoor_activity_schedule && (
                <p>
                  <span className="font-semibold text-slate-800">Outdoor schedule: </span>
                  {draft.outdoor_activity_schedule}
                </p>
              )}
              {draft.notes && (
                <p className={draft.outdoor_activity_schedule ? "mt-1" : ""}>
                  <span className="font-semibold text-slate-800">Preferences: </span>
                  {draft.notes}
                </p>
              )}
            </div>
          )}
        </div>
      ) : (
        <form onSubmit={handleSave} className="mt-4 space-y-4">
          <div className={`grid gap-3 ${compact ? "grid-cols-1" : "sm:grid-cols-2 lg:grid-cols-4"}`}>
            <div className={compact ? "" : "lg:col-span-2"}>
              <label className="block text-xs font-medium text-slate-700">
                City &amp; Location
              </label>
              <div className="mt-1 flex gap-2">
                <input
                  type="text"
                  required
                  maxLength={100}
                  value={draft.city}
                  onChange={(e) =>
                    setDraft((prev) => ({
                      ...prev,
                      city: e.target.value,
                      location_label: e.target.value,
                    }))
                  }
                  placeholder="e.g., Kolkata"
                  className="w-full rounded-xl border border-mist-200 px-3 py-2 text-sm focus:border-pine-600 focus:outline-none"
                />
                {presets.length > 0 && (
                  <select
                    aria-label="Quick city preset"
                    value={draft.location_id || ""}
                    onChange={(e) => {
                      const chosen = presets.find((p) => p.id === e.target.value);
                      if (chosen) {
                        setDraft((prev) => ({
                          ...prev,
                          location_id: chosen.id,
                          city: chosen.name,
                          location_label: [chosen.name, chosen.region, chosen.country]
                            .filter(Boolean)
                            .join(", "),
                        }));
                      }
                    }}
                    className="rounded-xl border border-mist-200 bg-white px-2.5 py-2 text-xs text-slate-700 focus:border-pine-600 focus:outline-none"
                  >
                    <option value="">Preset...</option>
                    {presets.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700">
                Household Size
              </label>
              <input
                type="number"
                min={1}
                max={20}
                value={draft.household_size}
                onChange={(e) =>
                  setDraft((prev) => ({
                    ...prev,
                    household_size: Math.max(1, Number(e.target.value) || 1),
                  }))
                }
                className="mt-1 w-full rounded-xl border border-mist-200 px-3 py-2 text-sm focus:border-pine-600 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700">
                Sensitivity Tier
              </label>
              <select
                value={draft.sensitivity_level}
                onChange={(e) =>
                  setDraft((prev) => ({ ...prev, sensitivity_level: e.target.value }))
                }
                className="mt-1 w-full rounded-xl border border-mist-200 bg-white px-3 py-2 text-sm focus:border-pine-600 focus:outline-none"
              >
                {SENSITIVITY_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className={`grid gap-3 ${compact ? "grid-cols-1" : "sm:grid-cols-2 lg:grid-cols-4"}`}>
            <div>
              <label className="block text-xs font-medium text-slate-700">
                Number of Children
              </label>
              <input
                type="number"
                min={0}
                max={20}
                value={draft.children_count}
                onChange={(e) =>
                  setDraft((prev) => ({
                    ...prev,
                    children_count: Math.max(0, Number(e.target.value) || 0),
                  }))
                }
                className="mt-1 w-full rounded-xl border border-mist-200 px-3 py-2 text-sm focus:border-pine-600 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700">
                Older Adults (60+)
              </label>
              <input
                type="number"
                min={0}
                max={20}
                value={draft.elderly_count}
                onChange={(e) =>
                  setDraft((prev) => ({
                    ...prev,
                    elderly_count: Math.max(0, Number(e.target.value) || 0),
                  }))
                }
                className="mt-1 w-full rounded-xl border border-mist-200 px-3 py-2 text-sm focus:border-pine-600 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700">
                Daily Commute Method
              </label>
              <select
                value={draft.commute_method}
                onChange={(e) =>
                  setDraft((prev) => ({ ...prev, commute_method: e.target.value }))
                }
                className="mt-1 w-full rounded-xl border border-mist-200 bg-white px-3 py-2 text-sm focus:border-pine-600 focus:outline-none"
              >
                {COMMUTE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700">
                Home Ventilation Preference
              </label>
              <select
                value={draft.ventilation_preference}
                onChange={(e) =>
                  setDraft((prev) => ({
                    ...prev,
                    ventilation_preference: e.target.value,
                  }))
                }
                className="mt-1 w-full rounded-xl border border-mist-200 bg-white px-3 py-2 text-sm focus:border-pine-600 focus:outline-none"
              >
                {VENTILATION_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid gap-2.5 sm:grid-cols-2">
            <label className="flex cursor-pointer items-center gap-2.5 rounded-xl border border-mist-200 bg-mist-50/70 px-3 py-2 text-xs font-medium text-slate-700">
              <input
                type="checkbox"
                checked={Boolean(draft.has_respiratory_condition)}
                onChange={() =>
                  setDraft((prev) => ({
                    ...prev,
                    has_respiratory_condition: !prev.has_respiratory_condition,
                  }))
                }
                className="h-4 w-4 rounded border-slate-300 text-pine-700 focus:ring-pine-600"
              />
              <span>Household has respiratory / asthma sensitivity</span>
            </label>

            <label className="flex cursor-pointer items-center gap-2.5 rounded-xl border border-mist-200 bg-mist-50/70 px-3 py-2 text-xs font-medium text-slate-700">
              <input
                type="checkbox"
                checked={Boolean(draft.has_air_purifier)}
                onChange={() =>
                  setDraft((prev) => ({
                    ...prev,
                    has_air_purifier: !prev.has_air_purifier,
                  }))
                }
                className="h-4 w-4 rounded border-slate-300 text-pine-700 focus:ring-pine-600"
              />
              <span>Indoor HEPA / air purifier available</span>
            </label>
          </div>

          <div className={`grid gap-3 ${compact ? "grid-cols-1" : "sm:grid-cols-2"}`}>
            <div>
              <label className="block text-xs font-medium text-slate-700">
                Typical Outdoor Activity Schedule
              </label>
              <input
                type="text"
                maxLength={240}
                value={draft.outdoor_activity_schedule}
                onChange={(e) =>
                  setDraft((prev) => ({
                    ...prev,
                    outdoor_activity_schedule: e.target.value,
                  }))
                }
                placeholder="e.g., School walk 8 AM, kids playground 5 PM"
                className="mt-1 w-full rounded-xl border border-mist-200 px-3 py-2 text-sm focus:border-pine-600 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700">
                Respiratory Sensitivity Context (Optional, non-medical)
              </label>
              <input
                type="text"
                maxLength={200}
                value={draft.respiratory_vulnerability}
                onChange={(e) =>
                  setDraft((prev) => ({
                    ...prev,
                    respiratory_vulnerability: e.target.value,
                  }))
                }
                placeholder="e.g., Dust or winter smog cough sensitivity (no names/records)"
                className="mt-1 w-full rounded-xl border border-mist-200 px-3 py-2 text-sm focus:border-pine-600 focus:outline-none"
              />
            </div>
          </div>

          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => {
                setFormError(null);
                setDraft(normalizeDraft(profile));
                setEditing(false);
              }}
              className="rounded-xl border border-mist-200 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-mist-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="rounded-xl bg-pine-700 px-4 py-2 text-xs font-semibold text-white hover:bg-pine-800 disabled:opacity-60"
            >
              {saving ? "Saving..." : "Save Profile"}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
