"use client";

import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/** Large amount input; currency comes from the selected account. */
export function AmountField({
  value,
  onChange,
  currency,
  error,
}: {
  value: string;
  onChange: (v: string) => void;
  currency?: string;
  error?: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <label htmlFor="txn-amount">
            Transaction Amount
            <span aria-hidden className="ml-0.5 text-fin-danger">*</span>
            <span className="sr-only"> (required)</span>
          </label>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-1.5">
        <div
          className={cn(
            "flex h-16 items-center gap-3 rounded-lg border bg-card px-3 transition-colors hover:border-text-muted",
            "focus-within:border-bank-accent focus-within:ring-2 focus-within:ring-bank-accent/40",
            error ? "border-fin-danger" : "border-border",
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
            value={value}
            aria-invalid={!!error}
            onChange={(e) => onChange(e.target.value)}
            className="h-full min-w-0 flex-1 bg-transparent text-right text-[26px] sm:text-[28px] font-semibold text-text-strong tabular-nums outline-none placeholder:text-text-muted/60"
          />
        </div>
        {error ? (
          <p role="alert" className="text-sm text-fin-danger">
            {error}
          </p>
        ) : (
          !currency && (
            <p className="text-xs text-text-muted">
              Currency follows the selected account.
            </p>
          )
        )}
      </CardContent>
    </Card>
  );
}
