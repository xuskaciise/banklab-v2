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
/** One-line amount: small muted currency code, then the number. */
function Money({ amount, currency }: { amount: number | string; currency: string }) {
  const full = formatMoney(amount, currency);
  const num = full.slice(currency.length).trim();
  return (
    <span
      title={full}
      className="flex min-w-0 items-baseline gap-1.5 text-xl whitespace-nowrap tabular-nums sm:text-2xl xl:text-3xl"
    >
      <span className="shrink-0 text-xs font-medium text-text-muted sm:text-sm">{currency}</span>
      <span className="truncate">{num}</span>
    </span>
  );
}
const CARD = "min-h-[112px] min-w-0";
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
            className={CARD}
            value={r ? <Money amount={r.vault_total} currency={c} /> : "—"}
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
            className={CARD}
            value={b ? <Money amount={b.balance} currency={c} /> : "—"}
            hint={t ? `Till ${t.till_code}` : "No till today"}
          />
        );
      })}
      {showTxn && (
        <StatCard
          label="Transactions"
          className={CARD}
          icon={Receipt}
          loading={txns.isPending}
          value={txns.data?.count ?? "—"}
          hint="Recorded in this session"
        />
      )}
      <StatCard
        label="Till status"
        className={CARD}
        icon={CircleDot}
        loading={mine.isPending}
        value={
          <span className="block truncate text-xl sm:text-2xl">
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
    <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-3">
      {has("vault.view") && <VaultKpis sid={sid} />}
      {isTeller && <TellerKpis sid={sid} showTxn={has("report.operational")} />}
      {pending.show && (
        <StatCard
          label="Pending approvals"
          className={CARD}
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
            className={CARD}
            icon={Store}
            loading={pending.sessionsLoading}
            value={pending.openTills}
            hint="Tellers currently serving"
          />
          <StatCard
            label="Till requests"
            className={CARD}
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
