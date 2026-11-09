import { cn } from "@/lib/utils";

/** Compact titled card used by the one-screen transaction layout. */
export function Panel({
  title,
  action,
  className,
  children,
}: {
  title?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <section
      className={cn(
        "rounded-xl border border-border bg-card p-3 shadow-xs",
        className,
      )}
    >
      {(title || action) && (
        <div className="mb-2 flex items-center justify-between gap-2">
          <h3 className="text-[13px] font-semibold text-text-strong">{title}</h3>
          {action}
        </div>
      )}
      <div className="space-y-3">{children}</div>
    </section>
  );
}
