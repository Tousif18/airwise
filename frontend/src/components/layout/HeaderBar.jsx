import { RefreshCw } from "lucide-react";
import DataStatusBadge from "../common/DataStatusBadge";
import { MobileMenuButton } from "./Sidebar";
import { formatTimestamp } from "../../utils/airQuality";

export default function HeaderBar({
  title,
  subtitle,
  dataStatus,
  isStale = false,
  fetchedAt,
  cachedAt,
  isRefreshing,
  refreshCooldownSeconds = 0,
  onRefresh,
  onOpenMobileMenu,
  mobileMenuOpen = false,
  mobileMenuButtonRef,
  showRefresh = true,
}) {
  const timestampDetail =
    dataStatus === "cached" && cachedAt
      ? `${isStale ? "Stale · " : ""}Cached ${formatTimestamp(cachedAt)}`
      : dataStatus === "live" && fetchedAt
        ? `Updated ${formatTimestamp(fetchedAt)}`
        : null;

  const refreshDisabled = isRefreshing || refreshCooldownSeconds > 0;

  return (
    <header className="sticky top-0 z-20 border-b border-mist-200 bg-white/90 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3.5 sm:px-6 lg:px-8">
        <div className="flex items-center gap-3">
          <MobileMenuButton
            onClick={onOpenMobileMenu}
            expanded={mobileMenuOpen}
            buttonRef={mobileMenuButtonRef}
          />
          <div>
            <h1 className="font-display text-lg font-bold text-slate-900 sm:text-xl">
              {title}
            </h1>
            <p className="text-xs text-slate-500 sm:text-sm">{subtitle}</p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          {showRefresh && (
            <>
              <DataStatusBadge status={dataStatus} detail={timestampDetail} />
              <button
                type="button"
                onClick={onRefresh}
                disabled={refreshDisabled}
                className="inline-flex items-center gap-1.5 rounded-xl border border-mist-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-xs transition hover:bg-mist-50 disabled:cursor-not-allowed disabled:opacity-60"
                title={
                  refreshCooldownSeconds > 0
                    ? `Please wait ${refreshCooldownSeconds}s before refreshing live telemetry again`
                    : "Fetch fresh live readings from Open-Meteo"
                }
              >
                <RefreshCw
                  className={`h-3.5 w-3.5 text-pine-700 ${
                    isRefreshing ? "animate-spin" : ""
                  }`}
                />
                <span className="hidden sm:inline">
                  {isRefreshing
                    ? "Refreshing..."
                    : refreshCooldownSeconds > 0
                      ? `Wait ${refreshCooldownSeconds}s`
                      : "Refresh Live"}
                </span>
              </button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
