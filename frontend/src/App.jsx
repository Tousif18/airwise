import { useCallback, useEffect, useState } from "react";
import Sidebar, { NAV_ITEMS } from "./components/layout/Sidebar";
import HeaderBar from "./components/layout/HeaderBar";
import DashboardPage from "./pages/DashboardPage";
import AiAssistantPage from "./pages/AiAssistantPage";
import IndoorAirGuidePage from "./pages/IndoorAirGuidePage";
import EnvironmentalImpactPage from "./pages/EnvironmentalImpactPage";
import {
  fetchAirQuality,
  fetchAssistantStatus,
  fetchFamilyProfile,
  fetchHealth,
  fetchPresetLocations,
  saveFamilyProfile,
  searchLocations,
} from "./services/api";

export default function App() {
  const [activePage, setActivePage] = useState("dashboard");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const [backendHealth, setBackendHealth] = useState(null);
  const [assistantStatus, setAssistantStatus] = useState(null);

  const [presets, setPresets] = useState([]);
  const [presetsLoading, setPresetsLoading] = useState(true);
  const [presetsError, setPresetsError] = useState(null);
  const [selectedLocation, setSelectedLocation] = useState(null);

  const [airQuality, setAirQuality] = useState(null);
  const [airQualityLoading, setAirQualityLoading] = useState(true);
  const [airQualityError, setAirQualityError] = useState(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const [familyProfile, setFamilyProfile] = useState(null);
  const [familyLoading, setFamilyLoading] = useState(true);
  const [familyError, setFamilyError] = useState(null);

  const loadAirQuality = useCallback(async (location, { forceRefresh = false } = {}) => {
    if (!location) return;
    if (forceRefresh) {
      setIsRefreshing(true);
    } else {
      setAirQualityLoading(true);
    }
    setAirQualityError(null);

    try {
      const data = await fetchAirQuality(location, { forceRefresh });
      setAirQuality(data);
    } catch (err) {
      setAirQualityError(
        err.message || "Unable to reach the AirWise backend for air quality telemetry."
      );
    } finally {
      setAirQualityLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  // Initial bootstrap: health, assistant readiness, preset locations, and family profile
  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      const [healthRes, assistantRes, presetsRes, familyRes] = await Promise.allSettled([
        fetchHealth(),
        fetchAssistantStatus(),
        fetchPresetLocations(),
        fetchFamilyProfile(),
      ]);

      if (cancelled) return;

      if (healthRes.status === "fulfilled") {
        setBackendHealth(healthRes.value);
      }

      if (assistantRes.status === "fulfilled") {
        setAssistantStatus(assistantRes.value);
      }

      if (presetsRes.status === "fulfilled") {
        const list = presetsRes.value?.locations || [];
        setPresets(list);
        setPresetsLoading(false);
        if (list.length > 0) {
          setSelectedLocation(list[0]);
        } else {
          setAirQualityLoading(false);
        }
      } else {
        setPresetsError(
          presetsRes.reason?.message || "Could not load preset monitoring locations."
        );
        setPresetsLoading(false);
        setAirQualityLoading(false);
        setAirQualityError("Backend connection unavailable. Start FastAPI on port 8000.");
      }

      if (familyRes.status === "fulfilled") {
        setFamilyProfile(familyRes.value);
      } else {
        setFamilyError(
          familyRes.reason?.message || "Could not load household profile from backend."
        );
      }
      setFamilyLoading(false);
    }

    bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  // Fetch Open-Meteo data whenever selected location changes
  useEffect(() => {
    if (selectedLocation) {
      loadAirQuality(selectedLocation);
    }
  }, [selectedLocation, loadAirQuality]);

  const handleSaveFamilyProfile = async (updatedProfile) => {
    setFamilyError(null);
    const saved = await saveFamilyProfile(updatedProfile);
    setFamilyProfile(saved);
    return saved;
  };

  const currentNav = NAV_ITEMS.find((item) => item.id === activePage) || NAV_ITEMS[0];

  return (
    <div className="flex min-h-screen bg-mist-50 text-slate-900">
      <Sidebar
        activePage={activePage}
        onSelectPage={setActivePage}
        mobileOpen={mobileMenuOpen}
        onToggleMobile={setMobileMenuOpen}
        backendHealth={backendHealth}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <HeaderBar
          title={currentNav.label}
          subtitle={
            activePage === "dashboard"
              ? "Real-time urban air quality monitoring for families"
              : currentNav.description
          }
          dataStatus={airQuality?.data_status || "unavailable"}
          fetchedAt={airQuality?.fetched_at}
          cachedAt={airQuality?.cached_at}
          isRefreshing={isRefreshing}
          onRefresh={() => loadAirQuality(selectedLocation, { forceRefresh: true })}
          onOpenMobileMenu={() => setMobileMenuOpen(true)}
          showRefresh={activePage === "dashboard"}
        />

        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-8">
          {activePage === "dashboard" && (
            <DashboardPage
              presets={presets}
              presetsLoading={presetsLoading}
              presetsError={presetsError}
              selectedLocation={selectedLocation}
              onSelectLocation={setSelectedLocation}
              onSearchLocations={searchLocations}
              airQuality={airQuality}
              airQualityLoading={airQualityLoading}
              airQualityError={airQualityError}
              onRetryAirQuality={() =>
                loadAirQuality(selectedLocation, { forceRefresh: true })
              }
              familyProfile={familyProfile}
              familyLoading={familyLoading}
              familyError={familyError}
              onSaveFamilyProfile={handleSaveFamilyProfile}
            />
          )}

          {activePage === "assistant" && (
            <AiAssistantPage
              assistantStatus={assistantStatus}
              selectedLocation={selectedLocation}
              familyProfile={familyProfile}
              onBackToDashboard={() => setActivePage("dashboard")}
            />
          )}

          {activePage === "indoor" && (
            <IndoorAirGuidePage
              onBackToDashboard={() => setActivePage("dashboard")}
            />
          )}

          {activePage === "impact" && (
            <EnvironmentalImpactPage
              onBackToDashboard={() => setActivePage("dashboard")}
            />
          )}
        </main>
      </div>
    </div>
  );
}
