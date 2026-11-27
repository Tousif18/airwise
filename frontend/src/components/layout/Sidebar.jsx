import { useEffect, useState } from "react";
import {
  Bot,
  Home,
  LayoutDashboard,
  Leaf,
  Menu,
  ShieldCheck,
  Wind,
  X,
} from "lucide-react";

export const NAV_ITEMS = [
  {
    id: "dashboard",
    label: "Dashboard",
    description: "Air quality & family overview",
    icon: LayoutDashboard,
    badge: null,
  },
  {
    id: "assistant",
    label: "AI Assistant",
    description: "Gemini & rule-based smog advice",
    icon: Bot,
    badge: null,
  },
  {
    id: "indoor",
    label: "Indoor Air Guide",
    description: "Home ventilation, kitchen & HEPA",
    icon: Home,
    badge: null,
  },
  {
    id: "impact",
    label: "Environmental Impact",
    description: "CO₂ avoided & trip tracker",
    icon: Leaf,
    badge: null,
  },
];

export default function Sidebar({
  activePage,
  onSelectPage,
  mobileOpen,
  onToggleMobile,
  backendHealth,
  closeButtonRef,
}) {
  const [isDesktop, setIsDesktop] = useState(() =>
    window.matchMedia("(min-width: 1024px)").matches
  );

  useEffect(() => {
    const desktopQuery = window.matchMedia("(min-width: 1024px)");
    const updateDesktopState = () => setIsDesktop(desktopQuery.matches);

    updateDesktopState();
    desktopQuery.addEventListener("change", updateDesktopState);

    return () => desktopQuery.removeEventListener("change", updateDesktopState);
  }, []);

  const handleSelect = (id) => {
    onSelectPage(id);
    if (mobileOpen) {
      onToggleMobile(false);
    }
  };

  return (
    <>
      {/* Mobile top bar trigger */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-slate-900/40 backdrop-blur-xs lg:hidden"
          onClick={() => onToggleMobile(false)}
          aria-hidden="true"
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-mist-200 bg-white transition-transform duration-200 lg:static lg:translate-x-0 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
        id="primary-navigation"
        role={mobileOpen && !isDesktop ? "dialog" : undefined}
        aria-label="Primary Navigation"
        aria-modal={mobileOpen && !isDesktop ? true : undefined}
        inert={!isDesktop && !mobileOpen ? true : undefined}
      >
        {/* Brand header */}
        <div className="flex items-center justify-between border-b border-mist-200 px-5 py-5">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-pine-700 text-white shadow-sm">
              <Wind className="h-5 w-5" />
            </div>
            <div>
              <span className="block font-display text-lg font-bold tracking-tight text-slate-900">
                AirWise
              </span>
              <span className="block text-[11px] font-medium text-pine-700">
                Urban Air Assistant
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={() => onToggleMobile(false)}
            className="rounded-lg p-1.5 text-slate-500 hover:bg-mist-100 lg:hidden"
            aria-label="Close navigation menu"
            ref={closeButtonRef}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Navigation links */}
        <nav className="flex-1 space-y-1.5 overflow-y-auto px-3 py-4">
          <p className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            Workspace
          </p>
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = activePage === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => handleSelect(item.id)}
                aria-current={isActive ? "page" : undefined}
                className={`group flex w-full items-center gap-3 rounded-xl px-3.5 py-2.5 text-left transition ${
                  isActive
                    ? "bg-pine-50 text-pine-900 ring-1 ring-pine-600/20"
                    : "text-slate-600 hover:bg-mist-50 hover:text-slate-900"
                }`}
              >
                <span
                  className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition ${
                    isActive
                      ? "bg-pine-700 text-white shadow-xs"
                      : "bg-mist-100 text-slate-600 group-hover:bg-mist-200"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-semibold">{item.label}</span>
                    {item.badge && (
                      <span className="rounded-full bg-mist-100 px-2 py-0.5 text-[10px] font-medium text-slate-600">
                        {item.badge}
                      </span>
                    )}
                  </div>
                  <p className="truncate text-[11px] text-slate-500">
                    {item.description}
                  </p>
                </div>
              </button>
            );
          })}
        </nav>

        {/* System capability footer */}
        <div className="border-t border-mist-200 p-4">
          <div className="rounded-xl bg-mist-50 p-3.5">
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-800">
              <ShieldCheck className="h-4 w-4 text-pine-700" />
              <span>Telemetry Integrity</span>
            </div>
            <p className="mt-1 text-[11px] leading-relaxed text-slate-600">
              {backendHealth?.status === "ok"
                ? "FastAPI connected · Open-Meteo source active. Live, cached, and unavailable states are explicitly tagged."
                : "Backend API unreachable. Readings remain unavailable until connection is restored."}
            </p>
          </div>
        </div>
      </aside>
    </>
  );
}

export function MobileMenuButton({ onClick, expanded, buttonRef }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center justify-center rounded-xl border border-mist-200 bg-white p-2 text-slate-700 shadow-xs hover:bg-mist-50 lg:hidden"
      aria-label="Open navigation menu"
      aria-controls="primary-navigation"
      aria-expanded={expanded}
      ref={buttonRef}
    >
      <Menu className="h-5 w-5" />
    </button>
  );
}
