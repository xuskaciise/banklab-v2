import { cn } from "@/lib/utils";

type Tone = "success" | "pending" | "danger" | "muted" | "info";

const TONE: Record<Tone, { badge: string; dot: string }> = {
  success: { badge: "bg-fin-success-bg text-fin-success-dark", dot: "bg-fin-success" },
  pending: { badge: "bg-fin-pending-bg text-fin-pending", dot: "bg-fin-pending" },
  danger: { badge: "bg-fin-danger-bg text-fin-danger", dot: "bg-fin-danger" },
  muted: { badge: "bg-hover text-text-muted", dot: "bg-text-muted" },
  info: { badge: "bg-bank-sky-light text-bank-primary", dot: "bg-bank-accent" },
};

/** Status -> tone, per docs/design/theme.md section 5. */
const STATUS_TONE: Record<string, Tone> = {
  posted: "success",
  completed: "success",
  active: "success",
  open: "success",
  pending_approval: "pending",
  pending: "pending",
  draft: "pending",
  rejected: "danger",
  reversed: "danger",
  failed: "danger",
  closed: "muted",
  archived: "muted",
  inactive: "muted",
};

const humanize = (s: string) => s.replace(/_/g, " ");

/** Text + dot + colour: status is never conveyed by colour alone. */
export function StatusBadge({
  status,
  label,
  tone,
  className,
}: {
  status: string;
  label?: string;
  tone?: Tone;
  className?: string;
}) {
  const t = TONE[tone ?? STATUS_TONE[status] ?? "muted"];
  return (
    <span
      className={cn(
        "inline-flex h-5 items-center gap-1.5 rounded-full px-2 text-xs font-medium whitespace-nowrap capitalize",
        t.badge,
        className,
      )}
    >
      <span aria-hidden="true" className={cn("size-1.5 rounded-full", t.dot)} />
      {label ?? humanize(status)}
    </span>
  );
}
