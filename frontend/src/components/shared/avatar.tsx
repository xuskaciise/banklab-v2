import { cn } from "@/lib/utils";

export function initialsOf(name?: string | null) {
  if (!name) return "?";
  const p = name.trim().split(/\s+/);
  return ((p[0]?.[0] ?? "") + (p.length > 1 ? p[p.length - 1][0] : "")).toUpperCase();
}

/** Initials avatar on a sky-light disc. */
export function Avatar({
  name,
  className,
}: {
  name?: string | null;
  className?: string;
}) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "flex size-8 shrink-0 items-center justify-center rounded-full bg-bank-sky-light text-xs font-semibold text-bank-primary",
        className,
      )}
    >
      {initialsOf(name)}
    </span>
  );
}
