import { CheckRow } from "@/components/eod/check-card";
import type { EodCheck } from "@/lib/api/types";

export function ChecksCard({
  checks,
  sid,
  isRunning,
}: {
  checks: EodCheck[];
  sid: string;
  isRunning: (i: number) => boolean;
}) {
  const passed = checks.filter((c) => c.ok).length;
  const pct = checks.length ? (passed / checks.length) * 100 : 0; // progress bar width only
  return (
    <section className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4">
        <h2 className="text-base font-semibold text-text-strong">Closing checks</h2>
        <div className="flex items-center gap-3">
          <span className="text-sm text-text-muted tabular-nums">
            {passed} of {checks.length} passed
          </span>
          <div
            role="progressbar"
            aria-label="Checks passed"
            aria-valuemin={0}
            aria-valuemax={checks.length}
            aria-valuenow={passed}
            className="h-1.5 w-28 overflow-hidden rounded-full bg-hover"
          >
            <div className="h-full rounded-full bg-fin-success transition-all" style={{ width: `${pct}%` }} />
          </div>
        </div>
      </div>
      <ul className="py-1">
        {checks.map((c, i) => (
          <CheckRow key={c.code} check={c} sid={sid} running={isRunning(i)} last={i === checks.length - 1} />
        ))}
      </ul>
    </section>
  );
}
