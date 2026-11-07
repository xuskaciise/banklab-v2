import { Skeleton } from "@/components/ui/skeleton";

/** Generic block placeholder for a loading panel. */
export function LoadingSkeleton({
  rows = 4,
  label = "Loading",
}: {
  rows?: number;
  label?: string;
}) {
  return (
    <div
      role="status"
      aria-label={label}
      className="space-y-3 rounded-xl border border-border bg-card p-4"
    >
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-5 w-full" style={{ opacity: 1 - i * 0.12 }} />
      ))}
      <span className="sr-only">{label}…</span>
    </div>
  );
}
