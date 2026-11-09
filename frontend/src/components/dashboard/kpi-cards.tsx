"use client";

import {
  Banknote,
  CircleDot,
  ClipboardCheck,
  Landmark,
  Receipt,
  Store,
  Wallet,
} from "lucide-react";
import { formatMoney, useVault } from "@/lib/banking";
import { STATUS_LABEL, useMyTellerSession } from "@/lib/tellers";
import { useTransactions } from "@/lib/transactions";
import { StatCard } from "@/components/shared/stat-card";
import type { usePending } from "./use-pending";

type Pending = ReturnType<typeof usePending>;
const amber = (n: number, v: React.ReactNode) =>
  n > 0 ? <span className="text-fin-pending">{v}</span> : v;

function VaultKpis({ sid }: { sid: string }) {
  const v = useVault(sid);
  return (
    <>
      {["USD", "SOS"].map((c) => {
        const r = v.data?.reconciliation.find((x) => x.currency === c);
        return (
          <StatCard
            key={c}
            label={`Vault ${c}`}
            icon={Landmark}
            loading={v.isPending}
            value={
              <span className="text-2xl">
                {r ? formatMoney(r.vault_total, c) : "—"}
              </span>
            }
            hint="Cash held in the vault"
          />
        );
      })}
    </>
  );
}

function TellerKpis({ sid, showTxn }: { sid: string; showTxn: boolean }) {
  const mine = useMyTellerSession(sid);
  const txns = useTransactions(sid, {}, showTxn);
  const t = mine.data;
  return (
    <>
      {["USD", "SOS"].map((c) => {
        const b = t?.balances.find((x) => x.currency === c);
        return (
          <StatCard
            key={c}
            label={`Till ${c}`}
            icon={Wallet}
            loading={mine.isPending}
            value={
              <span className="text-2xl">{b ? formatMoney(b.balance, c) : "—"}</span>
            }
            hint={t ? `Till ${t.till_code}` : "No till today"}
          />
        );
      })}
      {showTxn && (
        <StatCard
          label="Transactions"
          icon={Receipt}
          loading={txns.isPending}
          value={txns.data?.count ?? "—"}
          hint="Recorded in this session"
        />
      )}
      <StatCard
        label="Till status"
        icon={CircleDot}
        loading={mine.isPending}
        value={
          <span className="text-2xl">
            {t ? (STATUS_LABEL[t.status] ?? t.status) : "Not open"}
          </span>
        }
        hint="Your till today"
      />
    </>
  );
}

/** KPI row: each role only sees cards whose data it is allowed to load. */
export function KpiCards({
  sid,
  has,
  pending,
}: {
  sid: string;
  has: (c: string) => boolean;
  pending: Pending;
}) {
  const isTeller = has("till.open.request") || has("till.close");
  const isManager = has("till.open.approve") || has("till.close.approve");
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {has("vault.view") && <VaultKpis sid={sid} />}
      {isTeller && <TellerKpis sid={sid} showTxn={has("report.operational")} />}
      {pending.show && (
        <StatCard
          label="Pending approvals"
          icon={ClipboardCheck}
          loading={pending.loading}
          value={amber(pending.total, pending.total)}
          hint="Waiting for your decision"
        />
      )}
      {isManager && (
        <>
          <StatCard
            label="Open tills"
            icon={Store}
            loading={pending.sessionsLoading}
            value={pending.openTills}
            hint="Tellers currently serving"
          />
          <StatCard
            label="Till requests"
            icon={Banknote}
            loading={pending.sessionsLoading}
            value={amber(pending.tillRequestCount, pending.tillRequestCount)}
            hint="Opening or closing, waiting"
          />
        </>
      )}
    </div>
  );
}
