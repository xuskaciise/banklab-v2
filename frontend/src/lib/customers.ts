"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiBlob, apiFetch } from "@/lib/api/client";
import type {
  AddPartyIn,
  CustomerDetail,
  CustomerIn,
  CustomerOut,
  CustomerUpdateIn,
  DocumentIn,
  DocumentUpdateIn,
  KinIn,
  PagedCustomer,
  PartyUpdateIn,
} from "@/lib/api/types";

export const CUSTOMER_TYPES = [
  { value: "individual", label: "Individual" },
  { value: "joint", label: "Joint" },
  { value: "company", label: "Company" },
  { value: "ngo", label: "NGO" },
] as const;

export const typeLabel = (t: string) =>
  CUSTOMER_TYPES.find((x) => x.value === t)?.label ?? t;

export const RELATION_LABEL: Record<string, string> = {
  owner: "Owner",
  joint_holder: "Joint holder",
  signatory: "Signatory",
  director: "Director",
};

export const DOC_TYPES = [
  { value: "national_id", label: "National ID" },
  { value: "passport", label: "Passport" },
  { value: "local_letter", label: "Local letter" },
] as const;

export const docLabel = (t: string) =>
  DOC_TYPES.find((x) => x.value === t)?.label ?? t;

/** Display-only zero padding of the integer CIF number. */
export const formatCif = (n: number) => String(n).padStart(6, "0");

export const PAGE_SIZE = 25;

/** Where the customer API lives: student session route or staff bank route. */
export type CustomerScope =
  | { kind: "student"; sessionId: string }
  | { kind: "staff"; sessionId: string; bankId: string };

export const scopeBase = (s: CustomerScope) =>
  s.kind === "student"
    ? `/api/s/${s.sessionId}/customers`
    : `/api/sessions/${s.sessionId}/banks/${s.bankId}/customers`;

const scopeKey = (s: CustomerScope) =>
  s.kind === "student" ? [s.sessionId] : [s.sessionId, s.bankId];

export function useCustomers(
  scope: CustomerScope,
  p: { q: string; type: string; page: number },
  enabled = true,
) {
  const qs = new URLSearchParams({ page: String(p.page) });
  if (p.q) qs.set("q", p.q);
  if (p.type) qs.set("type", p.type);
  return useQuery({
    queryKey: ["customers", scope.kind, ...scopeKey(scope), p],
    queryFn: () =>
      apiFetch<PagedCustomer>(`${scopeBase(scope)}?${qs.toString()}`),
    enabled,
    placeholderData: (prev) => prev,
  });
}

export const useCustomer = (scope: CustomerScope, id: string, enabled = true) =>
  useQuery({
    queryKey: ["customer", scope.kind, ...scopeKey(scope), id],
    queryFn: () => apiFetch<CustomerDetail>(`${scopeBase(scope)}/${id}`),
    enabled,
  });

function useStudentMutation<V, R>(
  sessionId: string,
  customerId: string | undefined,
  fn: (v: V) => Promise<R>,
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["customers", "student", sessionId] });
      if (customerId)
        qc.invalidateQueries({
          queryKey: ["customer", "student", sessionId, customerId],
        });
    },
  });
}

export const useCreateCustomer = (sid: string) =>
  useStudentMutation(sid, undefined, (b: CustomerIn) =>
    apiFetch<CustomerOut>(`/api/s/${sid}/customers`, { method: "POST", json: b }),
  );

export const useUpdateCustomer = (sid: string, cid: string) =>
  useStudentMutation(sid, cid, (b: CustomerUpdateIn) =>
    apiFetch<CustomerDetail>(`/api/s/${sid}/customers/${cid}`, {
      method: "PATCH",
      json: b,
    }),
  );

export const useAddParty = (sid: string, cid: string) =>
  useStudentMutation(sid, cid, (b: AddPartyIn) =>
    apiFetch<CustomerDetail>(`/api/s/${sid}/customers/${cid}/parties`, {
      method: "POST",
      json: b,
    }),
  );

export const useUpdateParty = (sid: string, cid: string) =>
  useStudentMutation(sid, cid, (b: PartyUpdateIn & { id: string }) => {
    const { id, ...rest } = b;
    return apiFetch(`/api/s/${sid}/customers/${cid}/parties/${id}`, {
      method: "PATCH",
      json: rest,
    });
  });

export const useAddDocument = (sid: string, cid: string) =>
  useStudentMutation(sid, cid, (b: DocumentIn & { partyId: string }) => {
    const { partyId, ...rest } = b;
    return apiFetch(`/api/s/${sid}/customers/${cid}/parties/${partyId}/documents`, {
      method: "POST",
      json: rest,
    });
  });

export const useUpdateDocument = (sid: string, cid: string) =>
  useStudentMutation(
    sid,
    cid,
    (b: DocumentUpdateIn & { partyId: string; docId: string }) => {
      const { partyId, docId, ...rest } = b;
      return apiFetch(
        `/api/s/${sid}/customers/${cid}/parties/${partyId}/documents/${docId}`,
        { method: "PATCH", json: rest },
      );
    },
  );

export const useAddKin = (sid: string, cid: string) =>
  useStudentMutation(sid, cid, (b: KinIn & { partyId: string }) => {
    const { partyId, ...rest } = b;
    return apiFetch(`/api/s/${sid}/customers/${cid}/parties/${partyId}/next-of-kin`, {
      method: "POST",
      json: rest,
    });
  });

export const useUploadFile = (sid: string, cid: string) =>
  useStudentMutation(
    sid,
    cid,
    (v: { path: string; file: File; source?: string }) => {
      const form = new FormData();
      form.append("file", v.file);
      if (v.source) form.append("source", v.source);
      return apiFetch(`/api/s/${sid}/customers/${cid}/${v.path}`, {
        method: "POST",
        form,
      });
    },
  );

/** Loads a protected file as a blob URL (cookies are sent). */
export function useBlobUrl(path: string, enabled: boolean, version: unknown) {
  return useQuery({
    queryKey: ["customer-file", path, version],
    queryFn: async () => URL.createObjectURL(await apiBlob(path)),
    enabled,
    staleTime: Infinity,
    gcTime: 60_000,
  });
}
