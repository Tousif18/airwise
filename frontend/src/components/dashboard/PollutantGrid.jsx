import { Wind } from "lucide-react";
import PollutantCard from "./PollutantCard";
import { EmptyState, LoadingCardSkeleton } from "../common/StateFeedback";

export default function PollutantGrid({ pollutants = [], loading = false }) {
  return (
    <section aria-label="Pollutant Breakdown" className="space-y-3">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="font-display text-base font-bold text-slate-900 sm:text-lg">
            Key Urban Pollutants
          </h2>
          <p className="text-xs text-slate-500">
            Individual pollutant concentrations compared against WHO 24-hour reference guidelines.
          </p>
        </div>
      </div>

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, idx) => (
            <LoadingCardSkeleton key={idx} lines={3} />
          ))}
        </div>
      ) : pollutants.length === 0 ? (
        <EmptyState
          icon={Wind}
          title="No pollutant telemetry available"
          description="Select a monitoring location or refresh to query Open-Meteo pollutant sensors."
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {pollutants.map((pollutant) => (
            <PollutantCard key={pollutant.key} pollutant={pollutant} />
          ))}
        </div>
      )}
    </section>
  );
}
