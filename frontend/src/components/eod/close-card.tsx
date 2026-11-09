import { Lock } from "lucide-react";
import { dateLabel, nextDate } from "@/lib/eod";
import { Button } from "@/components/ui/button";

export function CloseCard({
  date,
  canClose,
  busy,
  onClose,
}: {
  date: string;
  canClose: boolean;
  busy: boolean;
  onClose: () => void;
}) {
  return (
    <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <h2 className="text-base font-semibold text-text-strong">Close business day</h2>
      <p className="mt-1 text-sm text-text-muted">
        Closing will lock {dateLabel(date)} and open {dateLabel(nextDate(date))}. This cannot be undone.
      </p>
      <Button className="mt-4 w-full" disabled={!canClose || busy} onClick={onClose}>
        <Lock className="size-4" aria-hidden /> Close day
      </Button>
      {!canClose && <p className="mt-2 text-xs text-text-muted">Fix the failed checks first.</p>}
    </section>
  );
}
