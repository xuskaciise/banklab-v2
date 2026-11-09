"use client";

import { useRef } from "react";
import { ArrowDownToLine, ArrowLeftRight, ArrowUpFromLine } from "lucide-react";
import { cn } from "@/lib/utils";

export type Kind = "deposit" | "withdrawal" | "transfer";

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
  transfer: {
    label: "Account Transfer",
    hint: "Transfer funds between accounts.",
    icon: ArrowLeftRight,
  },
};

/** Radio-group of transaction types; arrow keys move the selection. */
export function TypeSelector({
  kinds,
  value,
  onChange,
}: {
  kinds: Kind[];
  value: Kind;
  onChange: (k: Kind) => void;
}) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  function onKey(e: React.KeyboardEvent, i: number) {
    const step =
      e.key === "ArrowRight" || e.key === "ArrowDown"
        ? 1
        : e.key === "ArrowLeft" || e.key === "ArrowUp"
          ? -1
          : 0;
    if (!step) return;
    e.preventDefault();
    const next = kinds[(i + step + kinds.length) % kinds.length];
    onChange(next);
    refs.current[next]?.focus();
  }

  return (
    <div
      role="radiogroup"
      aria-label="Transaction type"
      className="grid gap-3 sm:grid-cols-3"
    >
      {kinds.map((k, i) => {
        const { label, hint, icon: Icon } = KIND_META[k];
        const active = k === value;
        return (
          <button
            key={k}
            ref={(el) => {
              refs.current[k] = el;
            }}
            type="button"
            role="radio"
            aria-checked={active}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(k)}
            onKeyDown={(e) => onKey(e, i)}
            className={cn(
              "flex items-start gap-3 rounded-xl border p-4 text-left transition-colors outline-none",
              "focus-visible:ring-2 focus-visible:ring-bank-accent focus-visible:ring-offset-2",
              active
                ? "border-bank-primary bg-bank-sky-light"
                : "border-border bg-card hover:border-bank-accent hover:bg-surface",
            )}
          >
            <span
              className={cn(
                "flex size-9 shrink-0 items-center justify-center rounded-lg",
                active ? "bg-bank-primary text-white" : "bg-surface text-bank-primary",
              )}
            >
              <Icon className="size-5" aria-hidden />
            </span>
            <span className="min-w-0">
              <span className="block text-sm font-semibold text-text-strong">
                {label}
              </span>
              <span className="block text-xs text-text-muted">{hint}</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}
