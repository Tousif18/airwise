import { Sparkles } from "lucide-react";

export default function PlaceholderPageLayout({
  icon: Icon,
  badge,
  title,
  description,
  statusCard,
  cards = [],
  onBackToDashboard,
}) {
  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-mist-200 bg-white p-6 shadow-xs">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-pine-50 text-pine-700">
              <Icon className="h-6 w-6" />
            </div>
            <div>
              <span className="inline-flex items-center gap-1 rounded-full border border-pine-600/20 bg-pine-50 px-2.5 py-0.5 text-[11px] font-semibold text-pine-800">
                <Sparkles className="h-3 w-3" />
                {badge}
              </span>
              <h2 className="mt-2 font-display text-xl font-bold text-slate-900">
                {title}
              </h2>
              <p className="mt-1 max-w-2xl text-sm leading-relaxed text-slate-600">
                {description}
              </p>
            </div>
          </div>

          {onBackToDashboard && (
            <button
              type="button"
              onClick={onBackToDashboard}
              className="self-start rounded-xl border border-mist-200 bg-mist-50 px-3.5 py-2 text-xs font-semibold text-slate-700 transition hover:bg-mist-100"
            >
              Back to Dashboard
            </button>
          )}
        </div>

        {statusCard && <div className="mt-5">{statusCard}</div>}
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        {cards.map((card) => {
          const CardIcon = card.icon;
          return (
            <article
              key={card.title}
              className="rounded-2xl border border-mist-200 bg-white p-5 shadow-xs"
            >
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-mist-100 text-pine-700">
                <CardIcon className="h-4 w-4" />
              </div>
              <h3 className="mt-3 text-sm font-semibold text-slate-900">
                {card.title}
              </h3>
              <p className="mt-1.5 text-xs leading-relaxed text-slate-600">
                {card.description}
              </p>
              <span className="mt-4 inline-block rounded-full bg-mist-100 px-2.5 py-0.5 text-[11px] font-medium text-slate-600">
                {card.statusLabel}
              </span>
            </article>
          );
        })}
      </section>
    </div>
  );
}
