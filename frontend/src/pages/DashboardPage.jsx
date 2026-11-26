import { ErrorBanner } from "../components/common/StateFeedback";
import AirQualityOverview from "../components/dashboard/AirQualityOverview";
import FamilyProfileCard from "../components/dashboard/FamilyProfileCard";
import LocationSelector from "../components/dashboard/LocationSelector";
import PollutantGrid from "../components/dashboard/PollutantGrid";

export default function DashboardPage({
  presets,
  presetsLoading,
  presetsError,
  selectedLocation,
  onSelectLocation,
  onSearchLocations,
  airQuality,
  airQualityLoading,
  airQualityError,
  onRetryAirQuality,
  familyProfile,
  familyLoading,
  familyError,
  onSaveFamilyProfile,
}) {
  return (
    <div className="space-y-6">
      {airQualityError && airQuality && (
        <ErrorBanner
          title="Live refresh failed"
          message={airQualityError}
          onRetry={onRetryAirQuality}
        />
      )}

      <LocationSelector
        presets={presets}
        presetsLoading={presetsLoading}
        presetsError={presetsError}
        selectedLocation={selectedLocation}
        onSelectLocation={onSelectLocation}
        onSearchLocations={onSearchLocations}
      />

      <AirQualityOverview
        airQuality={airQuality}
        loading={airQualityLoading}
        error={airQualityError}
        onRetry={onRetryAirQuality}
      />

      <PollutantGrid
        pollutants={airQuality?.pollutants || []}
        loading={airQualityLoading}
      />

      <FamilyProfileCard
        profile={familyProfile}
        loading={familyLoading}
        error={familyError}
        onSaveProfile={onSaveFamilyProfile}
      />
    </div>
  );
}
