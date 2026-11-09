import { Check, Lock } from "lucide-react";
import type { TillAvailability } from "@/lib/api/types";
import { cn } from "@/lib/utils";

export function TillStatus({ t }: { t: TillAvailability }) {
  return t.available ? (
    <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-fin-success-bg px-2 py-0.5 text-xs font-medium text-fin-success">
      <span className="size-1.5 rounded-full bg-fin-success" aria-hidden />
      Free
    </span>
  ) : (
    <span className="inline-flex max-w-36 shrink-0 items-center gap-1.5 rounded-full bg-fin-pending-bg px-2 py-0.5 text-xs font-medium text-fin-pending">
      <Lock className="size-3 shrink-0" aria-hidden />
      <span className="truncate">
        In use{t.in_use_by ? ` · ${t.in_use_by}` : ""}
      </span>
    </span>
  );
}

/** One listbox option: code + branch, address underneath, status on the right. */
export function TillOption({
  id,
  t,
  selected,
  active,
  onHover,
  onPick,
}: {
  id: string;
  t: TillAvailability;
  selected: boolean;
  active: boolean;
  onHover: () => void;
  onPick: () => void;
}) {
  return (
    <li
      id={id}
      role="option"
      aria-selected={selected}
      aria-disabled={!t.available}
      onMouseEnter={onHover}
      onClick={onPick}
      className={cn(
        "flex items-center gap-3 px-3 py-2.5 transition-colors",
        t.available ? "cursor-pointer" : "cursor-not-allowed bg-surface opacity-70",
        selected && "bg-bank-sky-light",
        active && t.available && !selected && "bg-hover",
      )}
    >
      <Check
        className={cn("size-4 shrink-0 text-bank-primary", !selected && "invisible")}
        aria-hidden
      />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm">
          <span className="font-mono font-semibold text-text-strong">{t.code}</span>
          <span className="text-text-body"> · {t.branch_name}</span>{" "}
          <span className="text-xs text-text-muted">{t.branch_code}</span>
        </span>
        <span className="block truncate text-xs text-text-muted">
          {t.branch_address || "No address"}
        </span>
      </span>
      <TillStatus t={t} />
    </li>
  );
}
