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
          <label htmlFor="txn-amount">Transaction Amount</label>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-1.5">
        <div
          className={cn(
            "flex items-center gap-3 rounded-lg border bg-card px-4 transition-colors",
            "focus-within:border-bank-accent focus-within:ring-2 focus-within:ring-bank-accent/40",
            error ? "border-fin-danger" : "border-border",
          )}
        >
          <span className="min-w-10 text-sm font-semibold text-text-muted">
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
            className="h-14 w-full bg-transparent text-right text-2xl font-semibold text-text-strong tabular-nums outline-none placeholder:text-text-muted/60"
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
