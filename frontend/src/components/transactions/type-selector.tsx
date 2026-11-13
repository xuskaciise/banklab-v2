"use client";

import { useRef } from "react";
import {
  ArrowDownToLine,
  ArrowLeftRight,
  ArrowUpFromLine,
  BookOpenCheck,
} from "lucide-react";
import { cn } from "@/lib/utils";

export type Kind = "deposit" | "withdrawal" | "cheque_withdrawal" | "transfer";

export const KIND_META: Record<
  Kind,
  { label: string; hint: string; icon: typeof ArrowDownToLine }
> = {
  deposit: {
    label: "Cash Deposit",
    hint: "Add funds to a customer account.",
    icon: ArrowDownToLine,
  },
  withdrawal: {
    label: "Cash Withdrawal",
    hint: "Withdraw funds from an account.",
    icon: ArrowUpFromLine,
  },
  cheque_withdrawal: {
    label: "Cheque Withdrawal",
    hint: "Pay out cash against a cheque.",
    icon: BookOpenCheck,
  },
  transfer: {
    label: "Account Transfer",
    hint: "Transfer funds between accounts.",
    icon: ArrowLeftRight,
  },
};

export const ALL_KINDS = Object.keys(KIND_META) as Kind[];

const NOT_ALLOWED_HINT =
  "Not allowed for your current role. Cash transactions need the Teller role; ask your instructor to assign it.";

/**
 * Segmented radio-group of all transaction types. Types the current role
 * cannot post stay visible but disabled, so students see why they are missing.
 * Arrow keys move between the allowed types.
 */
export function TypeSelector({
  allowed,
  value,
  onChange,
}: {
  allowed: Kind[];
  value: Kind;
  onChange: (k: Kind) => void;
}) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  function onKey(e: React.KeyboardEvent) {
    const step =
      e.key === "ArrowRight" || e.key === "ArrowDown"
        ? 1
        : e.key === "ArrowLeft" || e.key === "ArrowUp"
          ? -1
          : 0;
    if (!step || allowed.length === 0) return;
    e.preventDefault();
    const i = allowed.indexOf(value);
    const next = allowed[(i + step + allowed.length) % allowed.length];
    onChange(next);
    refs.current[next]?.focus();
  }

  return (
    <div className="flex flex-col gap-1">
      <span id="txn-type-label" className="text-xs font-medium text-text-muted">
        Transaction type
      </span>
      <div
        role="radiogroup"
        aria-labelledby="txn-type-label"
        className="inline-flex flex-wrap gap-0.5 rounded-lg border border-border bg-surface p-0.5"
      >
        {ALL_KINDS.map((k) => {
          const { label, hint, icon: Icon } = KIND_META[k];
          const enabled = allowed.includes(k);
          const active = enabled && k === value;
          return (
            <button
              key={k}
              ref={(el) => {
                refs.current[k] = el;
              }}
              type="button"
              role="radio"
              aria-checked={active}
              aria-disabled={!enabled}
              disabled={!enabled}
              tabIndex={active ? 0 : -1}
              title={enabled ? hint : NOT_ALLOWED_HINT}
              onClick={() => enabled && onChange(k)}
              onKeyDown={onKey}
              className={cn(
                "flex h-9 items-center gap-1.5 rounded-md px-3 text-sm font-medium transition-colors outline-none",
                "focus-visible:ring-2 focus-visible:ring-bank-accent",
                active
                  ? "bg-bank-primary text-white shadow-xs"
                  : enabled
                    ? "text-text-body hover:bg-hover"
                    : "cursor-not-allowed text-text-muted opacity-50",
              )}
            >
              <Icon className="size-4" aria-hidden />
              <span className="hidden sm:inline">{label}</span>
              <span className="sr-only sm:hidden">{label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
