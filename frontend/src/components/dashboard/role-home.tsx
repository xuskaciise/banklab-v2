"use client";

import { Check } from "lucide-react";
import { abilities, LIMIT_NOTE } from "@/lib/role-guide";
import { KpiCards } from "./kpi-cards";
import { PendingPreview } from "./pending-preview";
import { QuickActions } from "./quick-actions";
import { RecentActivity } from "./recent-activity";
import { usePending } from "./use-pending";

function Permissions({ codes, note }: { codes: string[]; note: boolean }) {
  const can = abilities(codes);
  if (!can.length) return null;
  return (
    <details className="group rounded-xl border border-border bg-card px-4 py-3 text-sm shadow-xs">
      <summary className="cursor-pointer rounded font-medium text-text-strong outline-none select-none focus-visible:ring-2 focus-visible:ring-bank-accent">
        What can I do in this role?
      </summary>
      <ul className="mt-3 grid gap-1.5 sm:grid-cols-2">
        {can.map((s) => (
          <li key={s} className="flex items-start gap-2 text-text-body">
            <Check className="mt-0.5 size-4 shrink-0 text-fin-success" aria-hidden />
            {s}
          </li>
        ))}
      </ul>
      {note && <p className="mt-3 border-t border-border pt-3 text-xs text-text-muted">{LIMIT_NOTE}</p>}
    </details>
  );
}

export function RoleHome({ sid, codes }: { sid: string; codes: string[] }) {
  const has = (c: string) => codes.includes(c);
  const pending = usePending(sid, has);
  const makes = has("txn.cash_deposit") || has("txn.transfer");
  const counts: Record<string, number> = {
    Approvals: pending.limitCount,
    Vault: pending.transferCount,
    Tills: pending.tillRequestCount,
  };
  const viewAll = has("approval.decide")
    ? `/s/${sid}/approvals`
    : has("vault.view")
      ? `/s/${sid}/vault`
      : `/s/${sid}/tills`;
  return (
    <div className="min-w-0 space-y-4">
      <KpiCards sid={sid} has={has} pending={pending} />
      <QuickActions sid={sid} has={has} counts={counts} />
      <div className="grid items-start gap-4 lg:grid-cols-2">
        {pending.show && (
          <PendingPreview items={pending.items} loading={pending.loading} viewAll={viewAll} />
        )}
        <RecentActivity sid={sid} has={has} />
        <Permissions codes={codes} note={makes} />
      </div>
    </div>
  );
}
