"use client";

import { AmountWords } from "@/components/shared/amount-words";
import { cn } from "@/lib/utils";
import { FieldLabel } from "./field-label";

/** Prominent amount input; currency comes from the selected account. */
export function AmountField({
  value,
  onChange,
  currency,
  error,
  disabled,
}: {
  value: string;
  onChange: (v: string) => void;
  currency?: string;
  error?: string;
  disabled?: boolean;
}) {
  return (
    <div className="space-y-1">
      <FieldLabel htmlFor="txn-amount" required>
        Transaction Amount
      </FieldLabel>
      <div
        className={cn(
          "flex h-14 items-center gap-3 rounded-lg border bg-card px-3 transition-colors hover:border-text-muted",
          "focus-within:border-bank-accent focus-within:ring-2 focus-within:ring-bank-accent/40",
          error ? "border-fin-danger" : "border-border",
          disabled && "bg-surface opacity-60 hover:border-border",
        )}
      >
        <span className="rounded-md border border-border bg-surface px-2.5 py-1 text-sm font-semibold text-text-strong">
          {currency ?? "--"}
        </span>
        <input
          id="txn-amount"
          inputMode="decimal"
          autoComplete="off"
          placeholder="0.00"
          disabled={disabled}
          value={value}
          aria-invalid={!!error}
          onChange={(e) => onChange(e.target.value)}
          className="h-full min-w-0 flex-1 bg-transparent text-right text-2xl font-semibold text-text-strong tabular-nums outline-none placeholder:text-text-muted/60 disabled:cursor-not-allowed"
        />
      </div>
      <AmountWords value={value} currency={currency} />
      {error ? (
        <p role="alert" className="text-xs text-fin-danger">
          {error}
        </p>
      ) : (
        !currency && (
          <p className="text-xs text-text-muted">Currency follows the selected account.</p>
        )
      )}
    </div>
  );
}
