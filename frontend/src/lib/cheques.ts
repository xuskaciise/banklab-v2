"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiFetch } from "@/lib/api/client";
import type { ChequeOut, ChequebookOut } from "@/lib/api/types";

export const LEAF_OPTIONS = [10, 25, 50] as const;

export const CHEQUE_STATUS_LABEL: Record<string, string> = {
  issued: "Issued",
  paid: "Paid",
  stopped: "Stopped",
};

const MESSAGES: Record<string, string> = {
  cheques_not_allowed: "This account's product does not allow cheques.",
  invalid_leaves: "Choose a chequebook of 10, 25 or 50 leaves.",
  account_not_active: "This account is not active.",
  not_found: "Cheque or account not found.",
  cheque_required: "Enter a cheque number.",
  cheque_wrong_account: "This cheque number does not belong to the selected account.",
  cheque_already_paid: "This cheque has already been paid.",
  cheque_stopped: "Payment on this cheque has been stopped.",
  cheque_not_issued: "This cheque number has not been issued.",
  cheque_in_use: "This cheque is already used by a pending withdrawal.",
};

/** Maps backend cheque error codes to clear messages; other errors pass through. */
export function chequeErrorFor(e: unknown): Error {
  if (e instanceof ApiError) {
    const code = (e.body as { code?: string } | undefined)?.code;
    if (code && MESSAGES[code]) return new Error(MESSAGES[code]);
  }
  return e instanceof Error ? e : new Error("Something went wrong");
}

const acct = (sid: string, aid: string) => `/api/s/${sid}/accounts/${aid}`;

export const useChequebooks = (sid: string, aid: string, enabled = true) =>
  useQuery({
    queryKey: ["chequebooks", sid, aid],
    queryFn: () => apiFetch<ChequebookOut[]>(`${acct(sid, aid)}/chequebooks`),
    enabled,
  });

export const useCheques = (sid: string, aid: string, status: string, enabled = true) =>
  useQuery({
    queryKey: ["cheques", sid, aid, status],
    queryFn: () =>
      apiFetch<ChequeOut[]>(
        `${acct(sid, aid)}/cheques${status ? `?status=${status}` : ""}`,
      ),
    enabled,
  });

export function useIssueChequebook(sid: string, aid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (leaves: number) =>
      apiFetch<ChequebookOut>(`${acct(sid, aid)}/chequebooks`, {
        method: "POST",
        json: { leaves },
      }).catch((e) => {
        throw chequeErrorFor(e);
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["chequebooks", sid, aid] });
      qc.invalidateQueries({ queryKey: ["cheques", sid, aid] });
    },
  });
}

export function useStopCheque(sid: string, aid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (a: { id: string; reason: string }) =>
      apiFetch<ChequeOut>(`/api/s/${sid}/cheques/${a.id}/stop`, {
        method: "POST",
        json: { reason: a.reason },
      }).catch((e) => {
        throw chequeErrorFor(e);
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cheques", sid, aid] }),
  });
}
