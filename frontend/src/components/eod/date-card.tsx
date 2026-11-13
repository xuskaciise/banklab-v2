import { ArrowRight, CalendarCheck } from "lucide-react";
import { dateLabel, nextDate } from "@/lib/eod";
import { StatusBadge } from "@/components/shared/status-badge";

export function DateCard({ date, failed }: { date: string; failed: number }) {
  return (
    <section className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-border bg-card p-5 shadow-sm">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
        <div className="flex items-center gap-3">
          <span className="flex size-11 items-center justify-center rounded-lg bg-bank-sky-light">
            <CalendarCheck className="size-6 text-bank-primary" aria-hidden />
          </span>
          <div>
            <p className="text-xs font-medium tracking-wider text-text-muted uppercase">Current business date</p>
            <p className="text-2xl font-bold text-text-strong">{dateLabel(date)}</p>
            <p className="text-xs text-text-muted tabular-nums">{date}</p>
          </div>
        </div>
        <ArrowRight className="hidden size-5 text-text-muted sm:block" aria-hidden />
        <div>
          <p className="text-xs font-medium tracking-wider text-text-muted uppercase">Next business date</p>
          <p className="text-base font-medium text-text-muted">{dateLabel(nextDate(date))}</p>
        </div>
      </div>
      {failed === 0 ? (
        <StatusBadge status="completed" label="Ready to close" className="h-7 px-3 text-sm" />
      ) : (
        <StatusBadge
          status="failed"
          label={`${failed} ${failed === 1 ? "issue" : "issues"} to fix`}
          className="h-7 px-3 text-sm"
        />
      )}
    </section>
  );
}
