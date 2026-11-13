import { RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { hhmm } from "@/lib/eod";
import { Button } from "@/components/ui/button";

export function EodHeader({
  updatedAt,
  busy,
  onRerun,
  showRerun,
}: {
  updatedAt: number;
  busy: boolean;
  onRerun: () => void;
  showRerun: boolean;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-xl font-semibold tracking-tight text-text-strong sm:text-2xl">End of day</h1>
        <p className="mt-0.5 text-sm text-text-muted">
          Run the closing checks, then close the business day and open the next one.
        </p>
      </div>
      {showRerun && (
        <div className="flex items-center gap-3 text-xs text-text-muted">
          <span>Last checked {hhmm(updatedAt)}</span>
          <Button variant="outline" onClick={onRerun} disabled={busy}>
            <RefreshCw className={cn("size-4", busy && "animate-spin")} aria-hidden /> Re-run checks
          </Button>
        </div>
      )}
    </div>
  );
}
