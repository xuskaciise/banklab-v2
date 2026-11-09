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

/** Compact segmented radio-group of transaction types; arrow keys move. */
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
      className="inline-flex rounded-lg border border-border bg-surface p-0.5"
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
            title={hint}
            onClick={() => onChange(k)}
            onKeyDown={(e) => onKey(e, i)}
            className={cn(
              "flex h-9 items-center gap-1.5 rounded-md px-3 text-sm font-medium transition-colors outline-none",
              "focus-visible:ring-2 focus-visible:ring-bank-accent",
              active
                ? "bg-bank-sky-light text-bank-primary shadow-xs ring-1 ring-bank-primary"
                : "text-text-body hover:bg-hover",
            )}
          >
            <Icon className="size-4" aria-hidden />
            <span className="hidden sm:inline">{label}</span>
            <span className="sr-only sm:hidden">{label}</span>
          </button>
        );
      })}
    </div>
  );
}
