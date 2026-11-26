import { Bot, CalendarClock, KeyRound, MessageSquare, ShieldAlert } from "lucide-react";
import PlaceholderPageLayout from "../components/common/PlaceholderPageLayout";

export default function AiAssistantPage({
  assistantStatus,
  selectedLocation,
  familyProfile,
  onBackToDashboard,
}) {
  const configured = Boolean(assistantStatus?.configured);

  const statusCard = (
    <div className="flex flex-col gap-3 rounded-xl border border-mist-200 bg-mist-50/80 p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-start gap-3">
        <KeyRound className="mt-0.5 h-5 w-5 shrink-0 text-pine-700" />
        <div>
          <p className="text-sm font-semibold text-slate-900">
            Google Gemini Integration Status:{" "}
            <span className={configured ? "text-emerald-700" : "text-amber-700"}>
              {configured ? "Environment Key Detected" : "Awaiting GEMINI_API_KEY"}
            </span>
          </p>
          <p className="mt-0.5 text-xs text-slate-600">
            {assistantStatus?.message ||
              "Configure GEMINI_API_KEY in backend/.env to enable interactive winter smog Q&A in the next milestone."}
          </p>
        </div>
      </div>
      <span className="self-start rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-600 ring-1 ring-mist-200 sm:self-auto">
        Model: {assistantStatus?.model || "gemini-2.5-flash"}
      </span>
    </div>
  );

  const cards = [
    {
      icon: MessageSquare,
      title: "Context-Aware Smog Q&A",
      description: `Will combine ${selectedLocation?.name || "selected city"} telemetry with ${
        familyProfile?.household_name || "your household profile"
      } to answer daily safety questions.`,
      statusLabel: "Planned · Milestone 2",
    },
    {
      icon: CalendarClock,
      title: "Commute & School Timing Advisor",
      description:
        "Evaluates hourly PM2.5 curves to suggest safer outdoor travel and exercise windows during winter inversions.",
      statusLabel: "Planned · Milestone 2",
    },
    {
      icon: ShieldAlert,
      title: "Mask & Exposure Guidance",
      description:
        "Tailors N95/KN95 and activity precautions when young children, seniors, or asthma triggers are flagged.",
      statusLabel: "Planned · Milestone 2",
    },
  ];

  return (
    <PlaceholderPageLayout
      icon={Bot}
      badge="Module Placeholder · Gemini API"
      title="AirWise AI Assistant"
      description="This workspace will host the Google Gemini conversational assistant, grounding personalized winter smog advice in live Open-Meteo telemetry and your household profile."
      statusCard={statusCard}
      cards={cards}
      onBackToDashboard={onBackToDashboard}
    />
  );
}
