"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiFetch } from "@/lib/api/client";
import type {
  AccountIn,
  AccountOut,
  KycItem,
  PagedAccount,
  ProductOut,
} from "@/lib/api/types";

export const ACCOUNT_PAGE_SIZE = 25;

/** Display-only zero padding of the integer account number. */
export const formatAccountNo = (n: number) => String(n).padStart(8, "0");

export const MANDATES = [
  { value: "any_one", label: "Any one signs" },
  { value: "all_jointly", label: "All sign jointly" },
] as const;

export const mandateLabel = (m: string) =>
  MANDATES.find((x) => x.value === m)?.label ?? m;

export const statusLabel = (s: string) =>
  s === "active" ? "Active" : s === "closed" ? "Closed" : s;

/** Pulls the kyc_missing list out of a 400 kyc_incomplete error. */
export function kycMissingFrom(e: unknown): KycItem[] {
  if (e instanceof ApiError && e.status === 400) {
    const b = e.body as { code?: string; kyc_missing?: KycItem[] } | undefined;
    if (b?.code === "kyc_incomplete" && Array.isArray(b.kyc_missing))
      return b.kyc_missing;
  }
  return [];
}

export function useProducts(sid: string, enabled = true) {
  return useQuery({
    queryKey: ["products", sid],
    queryFn: () => apiFetch<ProductOut[]>(`/api/s/${sid}/products`),
    enabled,
  });
}

export function useAccounts(
  sid: string,
  p: { customerId?: string; status?: string; q?: string; page?: number },
  enabled = true,
) {
  const qs = new URLSearchParams();
  if (p.customerId) qs.set("customer_id", p.customerId);
  if (p.status) qs.set("status", p.status);
  if (p.q) qs.set("q", p.q);
  if (p.page) qs.set("page", String(p.page));
  return useQuery({
    queryKey: ["accounts", sid, p],
    queryFn: () =>
      apiFetch<PagedAccount>(`/api/s/${sid}/accounts?${qs.toString()}`),
    enabled,
    placeholderData: (prev) => prev,
  });
}

export const useAccount = (sid: string, id: string, enabled = true) =>
  useQuery({
    queryKey: ["account", sid, id],
    queryFn: () => apiFetch<AccountOut>(`/api/s/${sid}/accounts/${id}`),
    enabled,
  });

export function useOpenAccount(sid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: AccountIn) =>
      apiFetch<AccountOut>(`/api/s/${sid}/accounts`, { method: "POST", json: b }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["accounts", sid] }),
  });
}

export function useCloseAccount(sid: string, id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<AccountOut>(`/api/s/${sid}/accounts/${id}/close`, {
        method: "POST",
      }),
    onSuccess: (data) => {
      qc.setQueryData(["account", sid, id], data);
      qc.invalidateQueries({ queryKey: ["accounts", sid] });
    },
  });
}
