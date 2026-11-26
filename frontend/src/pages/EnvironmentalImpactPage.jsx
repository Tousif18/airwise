import { Bike, Flame, Leaf, Users } from "lucide-react";
import PlaceholderPageLayout from "../components/common/PlaceholderPageLayout";

export default function EnvironmentalImpactPage({ onBackToDashboard }) {
  const cards = [
    {
      icon: Bike,
      title: "Low-Emission Daily Commutes",
      description:
        "Compare metro, carpool, and off-peak travel alternatives when local NO₂ and particulate pollution spike.",
      statusLabel: "Placeholder · Next Milestone",
    },
    {
      icon: Flame,
      title: "Clean Household Energy Habits",
      description:
        "Sustainable alternatives to open waste burning, high-emission heating, and peak-hour diesel generator use.",
      statusLabel: "Placeholder · Next Milestone",
    },
    {
      icon: Users,
      title: "Neighborhood Clean-Air Actions",
      description:
        "Community car-free school zones, green-corridor stewardship, and residential smog readiness pledges.",
      statusLabel: "Placeholder · Next Milestone",
    },
  ];

  return (
    <PlaceholderPageLayout
      icon={Leaf}
      badge="Module Placeholder · Sustainability"
      title="Environmental Impact & Alternatives"
      description="Sustainable daily alternatives empowering families and residential communities to cut local winter emissions while protecting household health."
      cards={cards}
      onBackToDashboard={onBackToDashboard}
    />
  );
}
