"use client";

import { useCashTransfers } from "@/lib/banking";
import { useTellerSessions } from "@/lib/tellers";
import { TYPE_LABEL, useApprovals } from "@/lib/transactions";
import { formatMoney } from "@/lib/banking";

export type PendingItem = {
  key: string;
  title: string;
  sub: string;
  amount?: string;
  at: string;
  href: string;
  kind: "transfer" | "limit" | "till";
};

/** Work waiting for this role's decision; counts come from list lengths only. */
export function usePending(sid: string, has: (c: string) => boolean) {
  const custodian = has("cash.vault.approve_custodian");
  const vaultMgr = has("cash.vault.approve_manager");
  const limits = has("approval.decide");
  const tillAppr = has("till.open.approve") || has("till.close.approve");
  const transfers = useCashTransfers(sid, custodian || vaultMgr);
  const approvals = useApprovals(sid, limits);
  const sessions = useTellerSessions(sid, tillAppr);

  const items: PendingItem[] = [];
  for (const t of transfers.data ?? []) {
    const mine =
      (custodian && t.status === "pending") ||
      (vaultMgr && t.status === "custodian_approved");
    if (!mine) continue;
    items.push({
      key: `t-${t.id}`,
      title: `${t.from_label} → ${t.to_label}`,
      sub: `Cash transfer · ${t.requested_by_name}`,
      amount: formatMoney(t.amount, t.currency),
      at: t.created_at,
      href: `/s/${sid}/vault`,
      kind: "transfer",
    });
  }
  for (const a of approvals.data ?? []) {
    const x = a.transaction;
    items.push({
      key: `a-${a.id}`,
      title: x ? `${TYPE_LABEL[x.type] ?? x.type} ${x.ref_no}` : a.reason,
      sub: `Above limit · ${a.requested_by_name}`,
      amount: x ? formatMoney(x.amount, x.currency) : undefined,
      at: a.created_at,
      href: `/s/${sid}/approvals`,
      kind: "limit",
    });
  }
  const tillReq = (sessions.data ?? []).filter(
    (s) => s.status === "pending_open" || s.status === "closing",
  );
  for (const s of tillReq) {
    items.push({
      key: `s-${s.id}`,
      title: `Till ${s.till_code} · ${s.status === "closing" ? "close" : "open"} request`,
      sub: `Till · ${s.teller_name ?? "Teller"}`,
      at: s.close_requested_at ?? s.open_requested_at,
      href: `/s/${sid}/tills`,
      kind: "till",
    });
  }
  items.sort((a, b) => b.at.localeCompare(a.at));

  const loading =
    (custodian || vaultMgr) && transfers.isPending
      ? true
      : limits && approvals.isPending
        ? true
        : tillAppr && sessions.isPending;
  const transferCount = items.filter((i) => i.kind === "transfer").length;
  return {
    items,
    loading: !!loading,
    total: items.length,
    transferCount,
    limitCount: approvals.data?.length ?? 0,
    tillRequestCount: tillReq.length,
    openTills: (sessions.data ?? []).filter((s) => s.status === "open").length,
    sessionsLoading: tillAppr && sessions.isPending,
    show: custodian || vaultMgr || limits || tillAppr,
  };
}
