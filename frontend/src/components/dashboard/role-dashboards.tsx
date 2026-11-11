"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { formatMoney } from "@/lib/banking";
import type { ManagerDashboard, TellerDashboard } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { StatusBadge } from "@/components/shared/status-badge";
import { StatCard } from "@/components/shared/stat-card";
import { Skeleton } from "@/components/ui/skeleton";

type Amt = { currency: string; amount: number | string };

const TILL_TONE: Record<string, "success" | "pending" | "muted" | "info"> = {
  open: "success",
  pending_open: "pending",
  closing: "pending",
  closed: "muted",
  none: "muted",
};
const TILL_LABEL: Record<string, string> = {
  none: "Not open",
  pending_open: "Open requested",
  open: "Open",
  closing: "Closing requested",
  closed: "Closed",
};

const APPROVAL_LABEL: Record<string, string> = {
  transaction_limit: "Transactions above limit",
  till_open: "Till open requests",
  till_close: "Till close requests",
  cash_transfer: "Cash transfers",
};

function Block({
  title,
  action,
  children,
}: {
  title: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-border bg-card shadow-xs">
      <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold text-text-strong">{title}</h2>
        {action}
      </div>
      <div className="space-y-4 p-4">{children}</div>
    </section>
  );
}

function LinkTo({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="inline-flex items-center gap-1 rounded text-xs font-medium text-bank-accent outline-none hover:underline focus-visible:ring-2 focus-visible:ring-bank-accent"
    >
      {children}
      <ArrowRight className="size-3.5" aria-hidden />
    </Link>
  );
}

const amber = (n: number, v: React.ReactNode) =>
  n > 0 ? <span className="text-fin-pending">{v}</span> : v;

function AmountList({ items, sign }: { items: Amt[]; sign?: "+" | "−" }) {
  if (!items.length) return <span className="text-text-muted">—</span>;
  return (
    <span className="flex flex-col gap-0.5 text-base">
      {items.map((a) => (
        <span
          key={a.currency}
          className={cn(
            "whitespace-nowrap tabular-nums",
            sign === "+" && "text-fin-success",
            sign === "−" && "text-fin-danger",
          )}
        >
          {sign} {formatMoney(a.amount, a.currency)}
        </span>
      ))}
    </span>
  );
}

export function TellerDashboardBlock({ sid, d }: { sid: string; d: TellerDashboard }) {
  const ts = d.teller_session;
  return (
    <Block
      title="My teller dashboard"
      action={<LinkTo href={`/s/${sid}/teller/till`}>Go to my till</LinkTo>}
    >
      <div className="flex flex-wrap items-center gap-3">
        <StatusBadge
          status={d.till_status}
          label={TILL_LABEL[d.till_status] ?? d.till_status}
          tone={TILL_TONE[d.till_status] ?? "muted"}
        />
        <span className="text-sm text-text-muted">
          {ts ? `Till ${ts.till_code} · ${ts.business_date}` : "You have no till session today."}
        </span>
      </div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-3">
        <StatCard
          label="Till cash"
          className="min-w-0"
          value={
            d.till_cash.length ? (
              <span className="flex flex-col gap-0.5 text-lg">
                {d.till_cash.map((c) => (
                  <span key={c.currency} className="whitespace-nowrap">
                    {formatMoney(c.amount, c.currency)}
                  </span>
                ))}
              </span>
            ) : (
              "—"
            )
          }
          hint="Cash in your till now"
        />
        <StatCard
          label="My transactions today"
          className="min-w-0"
          value={d.today.count}
          hint={
            d.today.pending_count > 0
              ? `${d.today.pending_count} waiting for approval`
              : "None waiting for approval"
          }
        />
        <StatCard
          label="Money in today"
          className="min-w-0"
          value={<AmountList items={d.today.total_in} sign="+" />}
          hint="Deposits received"
        />
        <StatCard
          label="Money out today"
          className="min-w-0"
          value={<AmountList items={d.today.total_out} sign="−" />}
          hint="Withdrawals paid"
        />
        <StatCard
          label="My pending approvals"
          className="min-w-0"
          value={amber(d.pending_approvals, d.pending_approvals)}
          hint="Your requests waiting for a manager"
        />
      </div>
    </Block>
  );
}

export function ManagerDashboardBlock({ sid, d }: { sid: string; d: ManagerDashboard }) {
  const bd = d.business_day;
  const hrefFor = (type: string) =>
    type === "transaction_limit"
      ? `/s/${sid}/approvals`
      : type === "cash_transfer"
        ? `/s/${sid}/vault`
        : `/s/${sid}/tills`;
  const totalPending = d.pending_approvals.reduce((n, p) => n + p.count, 0);
  return (
    <Block
      title="Branch dashboard"
      action={<LinkTo href={`/s/${sid}/tills`}>Tills</LinkTo>}
    >
      <div className="flex flex-wrap items-center gap-3">
        {bd ? (
          <>
            <span className="text-sm text-text-body">
              Business day <span className="font-medium tabular-nums">{bd.date}</span>
            </span>
            <StatusBadge status={bd.status} />
          </>
        ) : (
          <span className="text-sm text-text-muted">No business day yet.</span>
        )}
      </div>

      {d.cash && (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="bg-surface text-xs text-text-muted uppercase">
              <tr>
                <th scope="col" className="px-3 py-2 text-left font-medium">
                  Branch cash
                </th>
                <th scope="col" className="px-3 py-2 text-right font-medium">
                  Vault
                </th>
                <th scope="col" className="px-3 py-2 text-right font-medium">
                  Tills
                </th>
                <th scope="col" className="px-3 py-2 text-right font-medium">
                  Total
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {d.cash.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-3 py-4 text-center text-text-muted">
                    No cash recorded yet.
                  </td>
                </tr>
              ) : (
                d.cash.map((c) => (
                  <tr key={c.currency}>
                    <th scope="row" className="px-3 py-2 text-left font-medium text-text-strong">
                      {c.currency}
                    </th>
                    <td className="px-3 py-2 text-right whitespace-nowrap tabular-nums">
                      {formatMoney(c.vault, c.currency)}
                    </td>
                    <td className="px-3 py-2 text-right whitespace-nowrap tabular-nums">
                      {formatMoney(c.tills, c.currency)}
                    </td>
                    <td className="px-3 py-2 text-right font-semibold whitespace-nowrap text-text-strong tabular-nums">
                      {formatMoney(c.total, c.currency)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      <div className="grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-3">
        {d.open_tills != null && (
          <StatCard label="Open tills" className="min-w-0" value={d.open_tills} hint="Tellers serving now" />
        )}
        {d.closing_tills != null && (
          <StatCard
            label="Closing tills"
            className="min-w-0"
            value={amber(d.closing_tills, d.closing_tills)}
            hint="Waiting for close approval"
          />
        )}
        <StatCard
          label="Pending approvals"
          className="min-w-0"
          value={amber(totalPending, totalPending)}
          hint="Waiting for your decision"
        />
      </div>

      {d.pending_approvals.length > 0 && (
        <ul className="divide-y divide-border rounded-lg border border-border">
          {d.pending_approvals.map((p) => (
            <li key={p.type}>
              <Link
                href={hrefFor(p.type)}
                className="flex items-center justify-between gap-3 px-3 py-2 text-sm outline-none hover:bg-hover focus-visible:ring-2 focus-visible:ring-bank-accent"
              >
                <span className="text-text-body">{APPROVAL_LABEL[p.type] ?? p.type}</span>
                <span className="font-semibold text-fin-pending tabular-nums">{p.count}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Block>
  );
}

export function DashboardSkeleton() {
  return (
    <div className="space-y-3 rounded-xl border border-border bg-card p-4" role="status" aria-label="Loading dashboard">
      <Skeleton className="h-5 w-48" />
      <Skeleton className="h-20 w-full" />
    </div>
  );
}
