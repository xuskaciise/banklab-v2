import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

/** KPI tile. Pass only values that come from the API. */
export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  loading,
  className,
}: {
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  icon?: React.ComponentType<{ className?: string }>;
  loading?: boolean;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border border-border bg-card p-4 shadow-xs",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-medium tracking-wide text-text-muted uppercase">
          {label}
        </p>
        {Icon && (
          <span className="flex size-8 items-center justify-center rounded-lg bg-bank-sky-light text-bank-primary">
            <Icon className="size-4" />
          </span>
        )}
      </div>
      {loading ? (
        <Skeleton className="mt-3 h-8 w-16" />
      ) : (
        <p className="mt-2 text-3xl font-semibold tracking-tight text-text-strong tabular-nums">
          {value}
        </p>
      )}
      {hint && <p className="mt-1 text-xs text-text-muted">{hint}</p>}
    </div>
  );
}
