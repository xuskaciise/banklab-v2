import { dateLabel, hhmm } from "@/lib/eod";
import type { EodStatus } from "@/lib/api/types";

export function RecentClosings({ items }: { items: EodStatus["recent_closings"] }) {
  return (
    <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <h2 className="text-base font-semibold text-text-strong">Recent closings</h2>
      {items.length === 0 ? (
        <p className="mt-2 text-sm text-text-muted">No business day has been closed yet.</p>
      ) : (
        <ul className="mt-2 divide-y divide-border">
          {items.map((c) => (
            <li key={c.date} className="flex items-baseline justify-between gap-3 py-2">
              <div className="min-w-0">
                <p className="text-sm font-medium text-text-strong">{dateLabel(c.date)}</p>
                <p className="truncate text-xs text-text-muted">{c.closed_by_name}</p>
              </div>
              <span className="text-xs text-text-muted tabular-nums">{c.closed_at ? hhmm(c.closed_at) : "—"}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
