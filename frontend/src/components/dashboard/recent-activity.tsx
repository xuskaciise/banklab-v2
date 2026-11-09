"use client";

import { Activity } from "lucide-react";
import { actionLabel, relativeTime, useAudit } from "@/lib/lab";
import { TYPE_LABEL, useTransactions } from "@/lib/transactions";
import { formatMoney } from "@/lib/banking";

type Row = { key: string; title: string; sub: string; at: string };

function Card({ rows, loading }: { rows: Row[]; loading: boolean }) {
  return (
    <section className="rounded-xl border border-border bg-card p-4 shadow-xs">
      <h2 className="mb-2 text-sm font-semibold text-text-strong">Recent activity</h2>
      {loading ? (
        <p className="py-4 text-center text-sm text-text-muted">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="flex items-center justify-center gap-2 rounded-lg bg-surface py-5 text-sm text-text-muted">
          <Activity className="size-4" aria-hidden />
          Nothing has happened yet
        </p>
      ) : (
        <ul className="divide-y divide-border">
          {rows.map((r) => (
            <li key={r.key} className="flex items-center justify-between gap-3 py-2">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-text-strong">{r.title}</p>
                <p className="truncate text-xs text-text-muted">{r.sub}</p>
              </div>
              <span className="shrink-0 text-xs text-text-muted">{relativeTime(r.at)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function AuditActivity({ sid }: { sid: string }) {
  const q = useAudit(sid, 1, "");
  const rows = (q.data?.items ?? []).slice(0, 6).map((a) => ({
    key: a.id,
    title: actionLabel(a.action),
    sub: a.actor_username ?? "System",
    at: a.at,
  }));
  return <Card rows={rows} loading={q.isPending} />;
}

function TxnActivity({ sid }: { sid: string }) {
  const q = useTransactions(sid, {});
  const rows = (q.data?.items ?? []).slice(0, 5).map((t) => ({
    key: t.id,
    title: `${TYPE_LABEL[t.type] ?? t.type} · ${formatMoney(t.amount, t.currency)}`,
    sub: `${t.ref_no} · ${t.customer_name}`,
    at: t.created_at,
  }));
  return <Card rows={rows} loading={q.isPending} />;
}

/** Audit log for roles that may see it; tellers see their latest transactions. */
export function RecentActivity({
  sid,
  has,
}: {
  sid: string;
  has: (c: string) => boolean;
}) {
  if (has("audit.view")) return <AuditActivity sid={sid} />;
  if (has("report.operational")) return <TxnActivity sid={sid} />;
  return null;
}
