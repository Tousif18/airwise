import { useEffect, useRef, useState } from "react";
import { Loader2, MapPin, Search, X } from "lucide-react";

const SEARCH_DEBOUNCE_MS = 450;

export default function LocationSelector({
  presets = [],
  selectedLocation,
  onSelectLocation,
  onSearchLocations,
  presetsLoading = false,
  presetsError = null,
  onRetryPresets,
}) {
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState(null);
  const [hasSearched, setHasSearched] = useState(false);

  const lastSearchedRef = useRef("");
  const activeSearchIdRef = useRef(0);

  const executeSearch = async (rawQuery) => {
    const trimmed = rawQuery.trim();
    if (trimmed.length < 2) {
      setSearchError("Enter at least 2 characters to search a city.");
      return;
    }

    const searchId = ++activeSearchIdRef.current;
    lastSearchedRef.current = trimmed.toLowerCase();
    setSearching(true);
    setSearchError(null);
    setHasSearched(true);

    try {
      const response = await onSearchLocations(trimmed);
      if (searchId !== activeSearchIdRef.current) return;

      if (response.data_status === "unavailable") {
        setSearchResults([]);
        if (response.rate_limited) {
          setSearchError(
            response.error_detail ||
              `Open-Meteo city search rate limit reached. Wait ${
                response.retry_after_seconds || 60
              }s before retrying.`
          );
        } else {
          setSearchError(
            response.error_detail || "Geocoding service is currently unavailable."
          );
        }
      } else {
        setSearchResults(response.locations || []);
      }
    } catch (err) {
      if (searchId !== activeSearchIdRef.current) return;
      setSearchResults([]);
      setSearchError(err.message || "Unable to search locations.");
    } finally {
      if (searchId === activeSearchIdRef.current) {
        setSearching(false);
      }
    }
  };

  // Debounced auto-search while typing >= 2 characters
  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length < 2) {
      lastSearchedRef.current = "";
      return undefined;
    }
    if (trimmed.toLowerCase() === lastSearchedRef.current) {
      return undefined;
    }
    const timer = setTimeout(() => {
      executeSearch(trimmed);
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    await executeSearch(query);
  };

  const clearSearch = () => {
    activeSearchIdRef.current += 1;
    lastSearchedRef.current = "";
    setQuery("");
    setSearchResults([]);
    setSearchError(null);
    setHasSearched(false);
    setSearching(false);
  };

  return (
    <section
      aria-label="Location Selector"
      className="rounded-2xl border border-mist-200 bg-white p-5 shadow-xs"
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-pine-700">
            <MapPin className="h-3.5 w-3.5" />
            <span>Monitoring Location</span>
          </div>
          <p className="mt-1 text-sm text-slate-600">
            Choose a residential hub or search any city via Open-Meteo Geocoding.
          </p>
        </div>

        {/* City search form */}
        <form onSubmit={handleSubmit} className="flex w-full gap-2 lg:w-96">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search city (e.g., Chandigarh, London)..."
              aria-label="Search city location"
              className="w-full rounded-xl border border-mist-200 bg-mist-50/70 py-2 pl-9 pr-8 text-sm text-slate-900 placeholder:text-slate-400 focus:border-pine-600 focus:bg-white focus:outline-none focus:ring-2 focus:ring-pine-600/20"
            />
            {query && (
              <button
                type="button"
                onClick={clearSearch}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-700"
                aria-label="Clear search"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
          <button
            type="submit"
            disabled={searching}
            className="inline-flex items-center gap-1.5 rounded-xl bg-pine-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-pine-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {searching ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <span>Search</span>
            )}
          </button>
        </form>
      </div>

      {/* Preset city pills */}
      <div className="mt-4">
        {presetsLoading ? (
          <div className="flex flex-wrap gap-2">
            {Array.from({ length: 5 }).map((_, idx) => (
              <div
                key={idx}
                className="h-8 w-24 animate-pulse rounded-full bg-slate-100"
              />
            ))}
          </div>
        ) : presetsError ? (
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-xs text-rose-700">{presetsError}</p>
            {onRetryPresets && (
              <button
                type="button"
                onClick={onRetryPresets}
                className="rounded-lg border border-rose-200 px-2.5 py-1 text-xs font-semibold text-rose-800 transition hover:bg-rose-50 focus:outline-none focus:ring-2 focus:ring-rose-500/30"
              >
                Retry locations
              </button>
            )}
          </div>
        ) : presets.length === 0 ? (
          <p className="text-xs text-slate-500">
            No preset locations available. Use search to pick coordinates.
          </p>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium text-slate-500">Quick cities:</span>
            {presets.map((loc) => {
              const isSelected = selectedLocation?.id === loc.id;
              return (
                <button
                  key={loc.id}
                  type="button"
                  onClick={() => {
                    clearSearch();
                    onSelectLocation(loc);
                  }}
                  className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition ${
                    isSelected
                      ? "border-pine-700 bg-pine-700 text-white shadow-xs"
                      : "border-mist-200 bg-mist-50 text-slate-700 hover:border-pine-600/40 hover:bg-pine-50"
                  }`}
                >
                  <span>{loc.name}</span>
                  <span className={isSelected ? "text-pine-100" : "text-slate-400"}>
                    {loc.country}
                  </span>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Geocoding search results / empty / error feedback */}
      {searchError && (
        <p className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-800">
          {searchError}
        </p>
      )}

      {hasSearched && !searching && !searchError && searchResults.length === 0 && (
        <p className="mt-3 rounded-xl border border-mist-200 bg-mist-50 px-3 py-2 text-xs text-slate-600">
          No matching cities found for "{query.trim()}". Try another city name.
        </p>
      )}

      {searchResults.length > 0 && (
        <div className="mt-3 rounded-xl border border-mist-200 bg-mist-50/70 p-2">
          <p className="px-2 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Search Results
          </p>
          <div className="grid gap-1.5 sm:grid-cols-2 lg:grid-cols-3">
            {searchResults.map((loc) => {
              const isSelected = selectedLocation?.id === loc.id;
              return (
                <button
                  key={loc.id}
                  type="button"
                  onClick={() => {
                    onSelectLocation(loc);
                    clearSearch();
                  }}
                  className={`flex items-center justify-between rounded-lg border px-3 py-2 text-left text-xs transition ${
                    isSelected
                      ? "border-pine-700 bg-pine-50 text-pine-900"
                      : "border-transparent bg-white text-slate-700 hover:border-mist-200"
                  }`}
                >
                  <div className="min-w-0">
                    <p className="truncate font-semibold">{loc.name}</p>
                    <p className="truncate text-[11px] text-slate-500">
                      {[loc.region, loc.country].filter(Boolean).join(", ")}
                    </p>
                  </div>
                  <span className="ml-2 shrink-0 text-[10px] text-slate-400">
                    {loc.latitude.toFixed(2)}, {loc.longitude.toFixed(2)}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}
