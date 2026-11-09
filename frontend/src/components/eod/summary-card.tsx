import { formatMoney } from "@/lib/banking";
import type { EodStatus } from "@/lib/api/types";

const TYPES: [string, string][] = [
  ["cash_deposit", "Deposits"],
  ["cash_withdrawal", "Cash withdrawals"],
  ["cheque_withdrawal", "Cheque withdrawals"],
  ["transfer", "Transfers"],
];

function Row({ label, sub, value }: { label: string; sub?: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-2">
      <div className="min-w-0">
        <dt className="text-sm text-text-muted">{label}</dt>
        {sub && <dd className="text-xs text-text-muted">{sub}</dd>}
      </div>
      <dd className="whitespace-nowrap text-sm font-semibold text-text-strong tabular-nums">{value}</dd>
    </div>
  );
}

export function SummaryCard({ summary }: { summary: EodStatus["summary"] }) {
  const { teller_sessions: ts } = summary;
  return (
    <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <h2 className="text-base font-semibold text-text-strong">Today&apos;s summary</h2>
      <dl className="mt-2 divide-y divide-border">
        <Row
          label="Transactions"
          sub={summary.reversed_count > 0 ? `${summary.reversed_count} reversed` : undefined}
          value={String(summary.transactions_total)}
        />
        {TYPES.flatMap(([code, label]) =>
          summary.by_type
            .filter((t) => t.type === code)
            .map((t) => (
              <Row
                key={`${code}-${t.currency}`}
                label={`${label} ${t.currency}`}
                sub={`${t.count} ${t.count === 1 ? "transaction" : "transactions"}`}
                value={formatMoney(t.amount, t.currency)}
              />
            )),
        )}
        <Row label="Teller sessions closed" value={`${ts.closed} / ${ts.total}`} />
        {summary.vault_balances.map((v) => (
          <Row key={v.currency} label={`Closing vault ${v.currency}`} value={formatMoney(v.amount, v.currency)} />
        ))}
      </dl>
    </section>
  );
}
