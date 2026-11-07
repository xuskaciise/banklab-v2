"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import type {
  BranchIn,
  BranchOut,
  BranchUpdateIn,
  CashTransferOut,
  TillIn,
  TillOut,
  VaultOut,
} from "@/lib/api/types";

/** Display-only: groups an API decimal string ("1250.5") as "USD 1,250.50". */
export function formatMoney(amount: number | string, currency: string) {
  const s = String(amount);
  const neg = s.startsWith("-");
  const [int = "0", frac = ""] = s.replace("-", "").split(".");
  const grouped = int.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${currency} ${neg ? "-" : ""}${grouped}.${frac.padEnd(2, "0").slice(0, 2)}`;
}

const base = (sid: string, bid: string) =>
  `/api/sessions/${sid}/banks/${bid}/branches`;

export const useBranches = (sid: string, bid: string) =>
  useQuery({
    queryKey: ["branches", sid, bid],
    queryFn: () => apiFetch<BranchOut[]>(base(sid, bid)),
  });

export function useCreateBranch(sid: string, bid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: BranchIn) =>
      apiFetch<BranchOut>(base(sid, bid), { method: "POST", json: b }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["branches", sid, bid] }),
  });
}

export function useUpdateBranch(sid: string, bid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...b }: BranchUpdateIn & { id: string }) =>
      apiFetch<BranchOut>(`${base(sid, bid)}/${id}`, { method: "PATCH", json: b }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["branches", sid, bid] }),
  });
}

export const useTills = (sid: string, bid: string, branchId: string) =>
  useQuery({
    queryKey: ["tills", sid, bid, branchId],
    queryFn: () => apiFetch<TillOut[]>(`${base(sid, bid)}/${branchId}/tills`),
  });

export function useCreateTill(sid: string, bid: string, branchId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: TillIn) =>
      apiFetch<TillOut>(`${base(sid, bid)}/${branchId}/tills`, {
        method: "POST",
        json: b,
      }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["tills", sid, bid, branchId] }),
  });
}

// ---- student vault ----
export const useVault = (sid: string, enabled = true) =>
  useQuery({
    queryKey: ["vault", sid],
    queryFn: () => apiFetch<VaultOut>(`/api/s/${sid}/vault`),
    enabled,
  });

export const useCashTransfers = (sid: string, enabled = true) =>
  useQuery({
    queryKey: ["cash-transfers", sid],
    queryFn: () => apiFetch<CashTransferOut[]>(`/api/s/${sid}/cash-transfers`),
    enabled,
  });

export type TransferAction = "approve-custodian" | "approve-manager" | "reject";

export function useTransferAction(sid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      action,
      reason,
    }: {
      id: string;
      action: TransferAction;
      reason?: string;
    }) =>
      apiFetch<CashTransferOut>(`/api/s/${sid}/cash-transfers/${id}/${action}`, {
        method: "POST",
        json: action === "reject" ? { reason: reason ?? "" } : undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cash-transfers", sid] });
      qc.invalidateQueries({ queryKey: ["vault", sid] });
    },
  });
}
