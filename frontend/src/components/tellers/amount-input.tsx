"use client";

import { useLayoutEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import { FieldLabel } from "@/components/transactions/field-label";

const group = (digits: string) => digits.replace(/\B(?=(\d{3})+(?!\d))/g, ",");

/** Removes thousand separators: "1,250.50" -> "1250.50". */
export const stripAmount = (v: string) => v.replace(/,/g, "");

/** Empty is fine; otherwise digits with optional decimals (USD: max 2). */
export function amountValid(display: string, decimals: number) {
  const raw = stripAmount(display).trim();
  if (!raw) return true;
  return decimals
    ? new RegExp(`^\d+(\.\d{0,${decimals}})?$`).test(raw)
    : /^\d+$/.test(raw);
}

/** Digits only, live separators, USD 2 decimals / SOS whole numbers. */
function format(input: string, decimals: number) {
  const allowDot = decimals > 0;
  const cleaned = input.replace(allowDot ? /[^\d.]/g : /\D/g, "");
  const dot = cleaned.indexOf(".");
  const intPart = (dot < 0 ? cleaned : cleaned.slice(0, dot)).slice(0, 15);
  const frac = dot < 0 ? null : cleaned.slice(dot + 1).replace(/\./g, "").slice(0, decimals);
  return group(intPart) + (frac === null ? "" : `.${frac}`);
}

export function AmountInput({
  currency,
  decimals,
  value,
  onChange,
  describedBy,
}: {
  currency: string;
  decimals: number;
  value: string;
  onChange: (v: string) => void;
  describedBy?: string;
}) {
  const ref = useRef<HTMLInputElement>(null);
  const caret = useRef<number | null>(null);
  const id = `float-${currency}`;
  const invalid = !amountValid(value, decimals);
  const msg = `${id}-msg`;

  useLayoutEffect(() => {
    if (caret.current !== null && ref.current) {
      ref.current.setSelectionRange(caret.current, caret.current);
      caret.current = null;
    }
  });

  function change(e: React.ChangeEvent<HTMLInputElement>) {
    const el = e.target;
    const pos = el.selectionStart ?? el.value.length;
    const sig = (s: string) => s.replace(/,/g, "").length;
    const before = sig(el.value.slice(0, pos));
    const next = format(el.value, decimals);
    let i = 0;
    let seen = 0;
    while (i < next.length && seen < before) {
      if (next[i] !== ",") seen++;
      i++;
    }
    caret.current = i;
    onChange(next);
  }

  return (
    <div className="space-y-1.5">
      <FieldLabel htmlFor={id} optional>
        {currency} float
      </FieldLabel>
      <div
        className={cn(
          "flex h-14 items-center gap-3 rounded-lg border bg-card px-3 transition-colors focus-within:ring-2",
          invalid
            ? "border-fin-danger focus-within:ring-fin-danger/30"
            : "border-border hover:border-text-muted focus-within:border-bank-accent focus-within:ring-bank-accent/40",
        )}
      >
        <span className="rounded-md border border-border bg-surface px-2.5 py-1 text-sm font-semibold text-text-strong">
          {currency}
        </span>
        <input
          ref={ref}
          id={id}
          inputMode={decimals ? "decimal" : "numeric"}
          autoComplete="off"
          placeholder={decimals ? "0.00" : "0"}
          value={value}
          aria-invalid={invalid}
          aria-describedby={`${describedBy ?? ""} ${msg}`.trim()}
          onChange={change}
          className="h-full min-w-0 flex-1 bg-transparent text-right text-xl font-semibold text-text-strong tabular-nums outline-none placeholder:text-text-muted/60"
        />
      </div>
      <p id={msg} className={cn("text-xs", invalid ? "text-fin-danger" : "text-text-muted")}>
        {invalid
          ? decimals
            ? "Enter a valid amount with at most 2 decimals."
            : "Enter a whole number."
          : "Leave empty if no float is needed."}
      </p>
    </div>
  );
}
