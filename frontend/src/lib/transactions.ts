"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiBlob, apiFetch } from "@/lib/api/client";
import { chequeErrorFor } from "@/lib/cheques";
import type {
  AccountOut,
  ChequeWithdrawalIn,
  ApprovalOut,
  DepositIn,
  PagedAccount,
  PagedTransaction,
  TransactionOut,
  TransferIn,
  WithdrawalIn,
} from "@/lib/api/types";

export const TXN_PAGE_SIZE = 25;

export const TYPE_LABEL: Record<string, string> = {
  cash_deposit: "Cash deposit",
  cash_withdrawal: "Cash withdrawal",
  transfer: "Transfer",
  cheque_withdrawal: "Cheque withdrawal",
  reversal: "Reversal",
};

export const STATUS_LABEL: Record<string, string> = {
  pending_approval: "Pending approval",
  posted: "Posted",
  rejected: "Rejected",
  reversed: "Reversed",
};

const base = (sid: string) => `/api/s/${sid}/transactions`;

/** Finds an active account by its number (leading zeros allowed). */
export async function lookupAccount(
  sid: string,
  accountNo: string,
): Promise<AccountOut | null> {
  const n = Number(accountNo.trim());
  if (!Number.isInteger(n) || n <= 0) return null;
  const res = await apiFetch<PagedAccount>(
    `/api/s/${sid}/accounts?status=active&account_no=${n}`,
  );
  return res.items.find((a) => a.account_no === n) ?? null;
}

export type NewTxn =
  | { kind: "deposit"; body: DepositIn }
  | { kind: "withdrawal"; body: WithdrawalIn }
  | { kind: "cheque_withdrawal"; body: ChequeWithdrawalIn }
  | { kind: "transfer"; body: TransferIn };

function useRefresh(sid: string) {
  const qc = useQueryClient();
  return () => {
    for (const k of ["transactions", "approvals", "accounts", "account", "teller-session-me"])
      qc.invalidateQueries({ queryKey: [k] });
    void sid;
  };
}

export function useCreateTxn(sid: string) {
  const refresh = useRefresh(sid);
  return useMutation({
    mutationFn: (t: NewTxn) =>
      apiFetch<TransactionOut>(
        `${base(sid)}/${t.kind === "cheque_withdrawal" ? "cheque-withdrawal" : t.kind}`,
        { method: "POST", json: t.body },
      ).catch((e) => {
        throw chequeErrorFor(e);
      }),
    onSuccess: refresh,
  });
}

export function useTransactions(
  sid: string,
  p: { status?: string; type?: string; page?: number },
  enabled = true,
) {
  const qs = new URLSearchParams();
  if (p.status) qs.set("status", p.status);
  if (p.type) qs.set("type", p.type);
  qs.set("page", String(p.page ?? 1));
  return useQuery({
    queryKey: ["transactions", sid, p],
    queryFn: () => apiFetch<PagedTransaction>(`${base(sid)}?${qs.toString()}`),
    enabled,
    placeholderData: (prev) => prev,
  });
}

export function useReverseTxn(sid: string) {
  const refresh = useRefresh(sid);
  return useMutation({
    mutationFn: (a: { id: string; reason: string }) =>
      apiFetch<TransactionOut>(`${base(sid)}/${a.id}/reverse`, {
        method: "POST",
        json: { reason: a.reason },
      }),
    onSuccess: refresh,
  });
}

/** Opens the receipt PDF in a new tab (fetched with the session cookie). */
export async function openReceipt(sid: string, txnId: string) {
  const win = window.open("", "_blank");
  try {
    const blob = await apiBlob(`${base(sid)}/${txnId}/receipt.pdf`);
    const url = URL.createObjectURL(blob);
    if (win) win.location.href = url;
    else window.location.href = url;
  } catch (e) {
    win?.close();
    throw e;
  }
}

export const useApprovals = (sid: string, enabled = true) =>
  useQuery({
    queryKey: ["approvals", sid],
    queryFn: () =>
      apiFetch<ApprovalOut[]>(`/api/s/${sid}/approvals?status=pending`),
    enabled,
    refetchInterval: 15000,
  });

export function useDecideApproval(sid: string) {
  const refresh = useRefresh(sid);
  return useMutation({
    mutationFn: (a: { id: string; decision: "approve" | "reject"; note: string }) =>
      apiFetch<ApprovalOut>(`/api/s/${sid}/approvals/${a.id}/${a.decision}`, {
        method: "POST",
        json: { note: a.note },
      }),
    onSuccess: refresh,
  });
}

/** Saves the receipt PDF through a temporary download link. */
export async function downloadReceipt(sid: string, txnId: string, refNo: string) {
  const blob = await apiBlob(`${base(sid)}/${txnId}/receipt.pdf`);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `receipt-${refNo}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
