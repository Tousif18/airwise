import { AlertTriangle, Inbox, RefreshCw } from "lucide-react";

export function LoadingCardSkeleton({ lines = 3, className = "" }) {
  return (
    <div
      className={`animate-pulse rounded-2xl border border-mist-200 bg-white p-6 shadow-sm ${className}`}
      aria-busy="true"
      aria-label="Loading air quality data"
    >
      <div className="h-4 w-1/3 rounded bg-slate-200" />
      <div className="mt-4 space-y-3">
        {Array.from({ length: lines }).map((_, idx) => (
          <div
            key={idx}
            className={`h-3 rounded bg-slate-100 ${idx === lines - 1 ? "w-2/3" : "w-full"}`}
          />
        ))}
      </div>
    </div>
  );
}

export function ErrorBanner({ title = "Unable to load data", message, onRetry }) {
  return (
    <div
      role="alert"
      className="flex flex-col gap-3 rounded-2xl border border-rose-200 bg-rose-50/80 p-4 text-rose-900 sm:flex-row sm:items-center sm:justify-between"
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-rose-600" />
        <div>
          <p className="text-sm font-semibold">{title}</p>
          {message && <p className="mt-0.5 text-xs text-rose-800">{message}</p>}
        </div>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center justify-center gap-1.5 self-start rounded-xl border border-rose-300 bg-white px-3 py-1.5 text-xs font-semibold text-rose-800 transition hover:bg-rose-100 sm:self-auto"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({ icon: Icon = Inbox, title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-mist-200 bg-white/70 px-6 py-10 text-center">
      <div className="flex h-11 w-11 items-center justify-center rounded-full bg-mist-100 text-pine-700">
        <Icon className="h-5 w-5" />
      </div>
      <h3 className="mt-3 text-sm font-semibold text-slate-900">{title}</h3>
      {description && (
        <p className="mt-1 max-w-md text-xs leading-relaxed text-slate-600">
          {description}
        </p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
