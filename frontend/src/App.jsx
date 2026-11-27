import { useCallback, useEffect, useRef, useState } from "react";
import Sidebar, { NAV_ITEMS } from "./components/layout/Sidebar";
import HeaderBar from "./components/layout/HeaderBar";
import DashboardPage from "./pages/DashboardPage";
import AiAssistantPage from "./pages/AiAssistantPage";
import IndoorAirGuidePage from "./pages/IndoorAirGuidePage";
import EnvironmentalImpactPage from "./pages/EnvironmentalImpactPage";
import {
  fetchAirQuality,
  fetchAssistantHealth,
  fetchFamilyProfile,
  fetchHealth,
  fetchPresetLocations,
  loadLocalFamilyProfile,
  saveFamilyProfile,
  saveLocalFamilyProfile,
  searchLocations,
} from "./services/api";
import {
  DEFAULT_REFRESH_COOLDOWN_MS,
  RefreshCooldownTracker,
} from "./utils/requestControl";

function getLocationKey(loc) {
  if (!loc) return null;
  if (loc.latitude != null && loc.longitude != null) {
    return `${loc.latitude.toFixed(4)}:${loc.longitude.toFixed(4)}:${loc.timezone || "auto"}`;
  }
  return loc.id || null;
}

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
  const [refreshCooldownSeconds, setRefreshCooldownSeconds] = useState(0);

  const [familyProfile, setFamilyProfile] = useState(() => loadLocalFamilyProfile());
  const [familyLoading, setFamilyLoading] = useState(() => !loadLocalFamilyProfile());
  const [familyError, setFamilyError] = useState(null);

  const cooldownTrackerRef = useRef(
    new RefreshCooldownTracker({ defaultCooldownMs: DEFAULT_REFRESH_COOLDOWN_MS })
  );
  const isRefreshingRef = useRef(false);
  const lastFetchedLocationKeyRef = useRef(null);

  // Tick manual refresh cooldown timer once per second while active
  useEffect(() => {
    if (refreshCooldownSeconds <= 0) return undefined;
    const timer = setInterval(() => {
      setRefreshCooldownSeconds(cooldownTrackerRef.current.getRemainingSeconds());
    }, 1000);
    return () => clearInterval(timer);
  }, [refreshCooldownSeconds]);

  const loadAirQuality = useCallback(async (location, { forceRefresh = false } = {}) => {
    if (!location) return;
    if (forceRefresh) {
      if (isRefreshingRef.current || !cooldownTrackerRef.current.canRefresh()) {
        setRefreshCooldownSeconds(cooldownTrackerRef.current.getRemainingSeconds());
        return;
      }
      isRefreshingRef.current = true;
      setIsRefreshing(true);
    } else {
      setAirQualityLoading(true);
    }
    setAirQualityError(null);

    try {
      const data = await fetchAirQuality(location, { forceRefresh });
      setAirQuality(data);

      if (data?.rate_limited) {
        const remaining = cooldownTrackerRef.current.recordAttempt({
          retryAfterSeconds: data.retry_after_seconds,
        });
        setRefreshCooldownSeconds(remaining);
      } else if (forceRefresh) {
        const remaining = cooldownTrackerRef.current.recordAttempt();
        setRefreshCooldownSeconds(remaining);
      }
    } catch (err) {
      setAirQualityError(
        err.message || "Unable to reach the AirWise backend for air quality telemetry."
      );
      if (forceRefresh) {
        const remaining = cooldownTrackerRef.current.recordAttempt();
        setRefreshCooldownSeconds(remaining);
      }
    } finally {
      setAirQualityLoading(false);
      setIsRefreshing(false);
      isRefreshingRef.current = false;
    }
  }, []);

  // Initial bootstrap: health, assistant readiness, preset locations, and family profile
  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      const localProfile = loadLocalFamilyProfile();
      const [healthRes, assistantRes, presetsRes, familyRes] = await Promise.allSettled([
        fetchHealth(),
        fetchAssistantHealth(),
        fetchPresetLocations(),
        localProfile ? saveFamilyProfile(localProfile) : fetchFamilyProfile(),
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
          const preferred =
            localProfile?.location_id &&
            list.find((loc) => loc.id === localProfile.location_id);
          setSelectedLocation(preferred || list[0]);
        } else {
          setAirQualityLoading(false);
        }
      } else {
        setPresetsError(
          presetsRes.reason?.message || "Could not load preset monitoring locations."
        );
        setPresetsLoading(false);
        setAirQualityLoading(false);
        setAirQualityError("Backend connection unavailable. Check that FastAPI is running.");
      }

      if (familyRes.status === "fulfilled") {
        setFamilyProfile(familyRes.value);
        saveLocalFamilyProfile(familyRes.value);
      } else if (!localProfile) {
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

  // Fetch Open-Meteo data only when the logical location key actually changes
  const selectedLocationKey = getLocationKey(selectedLocation);
  useEffect(() => {
    if (!selectedLocation || !selectedLocationKey) return;
    if (lastFetchedLocationKeyRef.current === selectedLocationKey) return;
    lastFetchedLocationKeyRef.current = selectedLocationKey;
    loadAirQuality(selectedLocation);
  }, [selectedLocation, selectedLocationKey, loadAirQuality]);

  const handleSaveFamilyProfile = async (updatedProfile) => {
    setFamilyError(null);
    saveLocalFamilyProfile(updatedProfile);
    const saved = await saveFamilyProfile(updatedProfile);
    setFamilyProfile(saved);
    if (saved.location_id) {
      const matched = presets.find((loc) => loc.id === saved.location_id);
      if (matched && getLocationKey(matched) !== selectedLocationKey) {
        setSelectedLocation(matched);
      }
    }
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
          isStale={Boolean(airQuality?.is_stale)}
          fetchedAt={airQuality?.fetched_at}
          cachedAt={airQuality?.cached_at}
          isRefreshing={isRefreshing}
          refreshCooldownSeconds={refreshCooldownSeconds}
          onRefresh={() => loadAirQuality(selectedLocation, { forceRefresh: true })}
          onOpenMobileMenu={() => setMobileMenuOpen(true)}
          mobileMenuOpen={mobileMenuOpen}
          showRefresh={
            activePage === "dashboard" ||
            activePage === "assistant" ||
            activePage === "indoor"
          }
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
              refreshCooldownSeconds={refreshCooldownSeconds}
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
              airQuality={airQuality}
              presets={presets}
              familyProfile={familyProfile}
              familyLoading={familyLoading}
              familyError={familyError}
              onSaveFamilyProfile={handleSaveFamilyProfile}
              onBackToDashboard={() => setActivePage("dashboard")}
            />
          )}

          {activePage === "indoor" && (
            <IndoorAirGuidePage
              selectedLocation={selectedLocation}
              airQuality={airQuality}
              familyProfile={familyProfile}
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
