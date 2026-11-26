import { AlertCircle, Clock, Radio } from "lucide-react";

const STATUS_STYLES = {
  live: {
    label: "Live Data",
    classes: "bg-emerald-50 text-emerald-800 border-emerald-200",
    dot: "bg-emerald-500 animate-pulse",
    Icon: Radio,
  },
  cached: {
    label: "Cached Data",
    classes: "bg-sky-50 text-sky-800 border-sky-200",
    dot: "bg-sky-500",
    Icon: Clock,
  },
  unavailable: {
    label: "Unavailable",
    classes: "bg-slate-100 text-slate-700 border-slate-300",
    dot: "bg-slate-400",
    Icon: AlertCircle,
  },
};

export default function DataStatusBadge({ status = "unavailable", detail = null, compact = false }) {
  const config = STATUS_STYLES[status] || STATUS_STYLES.unavailable;
  const { Icon } = config;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${config.classes}`}
      title={detail || config.label}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${config.dot}`} />
      <Icon className="h-3.5 w-3.5 shrink-0" />
      <span>{compact ? config.label.replace(" Data", "") : config.label}</span>
      {detail && !compact && (
        <span className="hidden sm:inline text-[11px] opacity-80">· {detail}</span>
      )}
    </span>
  );
}
