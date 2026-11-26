import { useEffect, useState } from "react";
import { Check, Edit3, HeartPulse, Shield, Users } from "lucide-react";
import { LoadingCardSkeleton } from "../common/StateFeedback";

const SENSITIVITY_OPTIONS = [
  { value: "standard", label: "Standard" },
  { value: "moderate", label: "Moderate (Children / Seniors)" },
  { value: "high", label: "High (Asthma / Respiratory)" },
];

export default function FamilyProfileCard({
  profile,
  loading,
  error,
  onSaveProfile,
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(profile);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState(null);

  useEffect(() => {
    if (profile) {
      setDraft(profile);
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

  const handleToggle = (field) => {
    setDraft((prev) => ({ ...prev, [field]: !prev[field] }));
  };

  const handleSave = async (event) => {
    event.preventDefault();
    setSaving(true);
    setSaveMessage(null);
    try {
      await onSaveProfile(draft);
      setEditing(false);
      setSaveMessage("Saved");
      setTimeout(() => setSaveMessage(null), 2500);
    } catch (err) {
      setSaveMessage(err.message || "Failed to save profile");
    } finally {
      setSaving(false);
    }
  };

  const activeFlags = [
    draft.has_young_children && "Young Children",
    draft.has_older_adults && "Older Adults",
    draft.has_respiratory_condition && "Respiratory Sensitivity",
    draft.daily_outdoor_commute && "Daily Commute",
    draft.has_hepa_purifier && "HEPA Purifier",
  ].filter(Boolean);

  return (
    <section
      aria-label="Family Profile"
      className="rounded-2xl border border-mist-200 bg-white p-5 shadow-xs"
    >
      <div className="flex flex-col gap-3 border-b border-mist-100 pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-pine-50 text-pine-700">
            <Users className="h-5 w-5" />
          </div>
          <div>
            <h2 className="font-display text-base font-bold text-slate-900">
              Family &amp; Household Profile
            </h2>
            <p className="text-xs text-slate-500">
              Personalizes future Gemini recommendations for your household.
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
            onClick={() => setEditing((prev) => !prev)}
            className="inline-flex items-center gap-1.5 rounded-xl border border-mist-200 bg-mist-50 px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:bg-mist-100"
          >
            <Edit3 className="h-3.5 w-3.5" />
            {editing ? "Cancel" : "Edit Profile"}
          </button>
        </div>
      </div>

      {error && (
        <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          {error}
        </p>
      )}

      {!editing ? (
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <div className="rounded-xl bg-mist-50 p-3.5">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Household
            </p>
            <p className="mt-1 text-sm font-semibold text-slate-900">
              {draft.household_name}
            </p>
            <p className="mt-0.5 text-xs text-slate-600">
              {draft.member_count} {draft.member_count === 1 ? "member" : "members"}
            </p>
          </div>

          <div className="rounded-xl bg-mist-50 p-3.5">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Sensitivity Tier
            </p>
            <div className="mt-1 flex items-center gap-1.5 text-sm font-semibold capitalize text-slate-900">
              <HeartPulse className="h-4 w-4 text-pine-700" />
              <span>{draft.sensitivity_level}</span>
            </div>
            <p className="mt-0.5 text-xs text-slate-600">
              {draft.has_hepa_purifier
                ? "Indoor HEPA filtration available"
                : "No indoor HEPA purifier listed"}
            </p>
          </div>

          <div className="rounded-xl bg-mist-50 p-3.5">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Active Household Factors
            </p>
            {activeFlags.length === 0 ? (
              <p className="mt-1 text-xs text-slate-500">
                No special vulnerability flags selected.
              </p>
            ) : (
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
            )}
          </div>

          {draft.notes && (
            <div className="rounded-xl border border-mist-100 bg-white px-3.5 py-2.5 text-xs text-slate-600 md:col-span-3">
              <span className="font-semibold text-slate-800">Routine note: </span>
              {draft.notes}
            </div>
          )}
        </div>
      ) : (
        <form onSubmit={handleSave} className="mt-4 space-y-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <label className="block text-xs font-medium text-slate-700">
                Household Name
              </label>
              <input
                type="text"
                required
                value={draft.household_name}
                onChange={(e) =>
                  setDraft((prev) => ({ ...prev, household_name: e.target.value }))
                }
                className="mt-1 w-full rounded-xl border border-mist-200 px-3 py-2 text-sm focus:border-pine-600 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700">
                Household Members
              </label>
              <input
                type="number"
                min={1}
                max={20}
                value={draft.member_count}
                onChange={(e) =>
                  setDraft((prev) => ({
                    ...prev,
                    member_count: Math.max(1, Number(e.target.value) || 1),
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

          <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
            {[
              ["has_young_children", "Young children at home"],
              ["has_older_adults", "Older adults (60+)"],
              ["has_respiratory_condition", "Asthma or respiratory sensitivity"],
              ["daily_outdoor_commute", "Daily outdoor school/work commute"],
              ["has_hepa_purifier", "HEPA air purifier available"],
            ].map(([field, label]) => (
              <label
                key={field}
                className="flex cursor-pointer items-center gap-2.5 rounded-xl border border-mist-200 bg-mist-50/70 px-3 py-2 text-xs font-medium text-slate-700"
              >
                <input
                  type="checkbox"
                  checked={Boolean(draft[field])}
                  onChange={() => handleToggle(field)}
                  className="h-4 w-4 rounded border-slate-300 text-pine-700 focus:ring-pine-600"
                />
                <span>{label}</span>
              </label>
            ))}
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700">
              Schedule or Sensitivity Notes
            </label>
            <input
              type="text"
              maxLength={280}
              value={draft.notes || ""}
              onChange={(e) =>
                setDraft((prev) => ({ ...prev, notes: e.target.value }))
              }
              placeholder="e.g., Morning school walk at 8:00 AM"
              className="mt-1 w-full rounded-xl border border-mist-200 px-3 py-2 text-sm focus:border-pine-600 focus:outline-none"
            />
          </div>

          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => {
                setDraft(profile);
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
              {saving ? "Saving..." : "Save Household Profile"}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
