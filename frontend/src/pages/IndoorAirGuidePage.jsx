import { Fan, Home, ShieldCheck, Wind } from "lucide-react";
import PlaceholderPageLayout from "../components/common/PlaceholderPageLayout";

export default function IndoorAirGuidePage({ onBackToDashboard }) {
  const cards = [
    {
      icon: Wind,
      title: "Smart Ventilation Windows",
      description:
        "Guidance on when to open cross-ventilation windows versus sealing rooms during peak morning and evening smog inversions.",
      statusLabel: "Placeholder · Next Milestone",
    },
    {
      icon: Fan,
      title: "HEPA & DIY Air Cleaning",
      description:
        "Room-size CADR sizing calculators, filter replacement reminders, and low-cost Corsi-Rosenthal box setup guides.",
      statusLabel: "Placeholder · Next Milestone",
    },
    {
      icon: ShieldCheck,
      title: "Indoor Source Reduction",
      description:
        "Practical kitchen exhaust, incense/smoke avoidance, and indoor humidity checklists tailored to urban apartments.",
      statusLabel: "Placeholder · Next Milestone",
    },
  ];

  return (
    <PlaceholderPageLayout
      icon={Home}
      badge="Module Placeholder · Indoor Guidance"
      title="Indoor Air Quality Guide"
      description="Actionable indoor protection playbooks to help urban households reduce indoor PM2.5 intrusion when outdoor winter smog spikes."
      cards={cards}
      onBackToDashboard={onBackToDashboard}
    />
  );
}
