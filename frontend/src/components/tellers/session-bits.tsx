"use client";

import { formatMoney } from "@/lib/banking";
import { STATUS_LABEL } from "@/lib/tellers";
import type { CashCount, TellerSession } from "@/lib/api/types";
import { StatusBadge } from "@/components/shared/status-badge";

export const CURRENCIES = ["USD", "SOS"] as const;

export function SessionStatus({ status }: { status: string }) {
  const tone =
    status === "pending_open" || status === "closing" ? "pending" : undefined;
  return (
    <StatusBadge
      status={status}
      label={STATUS_LABEL[status] ?? status}
      tone={tone}
    />
  );
}

/** Over/short: the sign and a word are always shown, never colour alone. */
export function Difference({
  value,
  currency,
}: {
  value: number | string;
  currency: string;
}) {
  const n = Number(value);
  const label = n === 0 ? "Balanced" : n > 0 ? "Over" : "Short";
  const cls =
    n === 0
      ? "text-text-muted"
      : n > 0
        ? "text-fin-success"
        : "text-fin-danger";
  return (
    <span className={`font-medium tabular-nums ${cls}`}>
      {n > 0 ? "+" : ""}
      {formatMoney(value, currency)} <span className="text-xs">({label})</span>
    </span>
  );
}

export function Balances({ s }: { s: TellerSession }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {CURRENCIES.map((c) => {
        const b = s.balances.find((x) => x.currency === c);
        return (
          <div
            key={c}
            className="rounded-xl border border-border bg-card p-4 shadow-xs"
          >
            <p className="text-xs font-medium tracking-wide text-text-muted uppercase">
              Till cash {c}
            </p>
            <p className="mt-2 text-2xl font-semibold text-text-strong tabular-nums">
              {formatMoney(b?.balance ?? "0", c)}
            </p>
          </div>
        );
      })}
    </div>
  );
}

/** Closing count result per currency, with the count lines. */
export function CountSummary({ counts }: { counts: CashCount[] }) {
  if (!counts.length) return null;
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {counts.map((c) => (
        <div
          key={c.id}
          className="space-y-2 rounded-xl border border-border bg-card p-4 text-sm shadow-xs"
        >
          <p className="font-semibold text-text-strong">
            {c.currency} count (attempt {c.attempt})
          </p>
          <ul className="space-y-0.5 text-xs text-text-muted">
            {c.lines
              .filter((l) => l.quantity > 0)
              .map((l) => (
                <li
                  key={l.denomination_id}
                  className="flex justify-between tabular-nums"
                >
                  <span>
                    {l.value} × {l.quantity}
                  </span>
                </li>
              ))}
          </ul>
          <dl className="space-y-1 border-t border-border pt-2">
            <div className="flex justify-between">
              <dt className="text-text-muted">Counted</dt>
              <dd className="tabular-nums">
                {formatMoney(c.counted_total, c.currency)}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-text-muted">System</dt>
              <dd className="tabular-nums">
                {formatMoney(c.system_total, c.currency)}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-text-muted">Difference</dt>
              <dd>
                <Difference value={c.difference} currency={c.currency} />
              </dd>
            </div>
          </dl>
        </div>
      ))}
    </div>
  );
}
