"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import type {
  CloseCountIn,
  DenominationOut,
  OpenRequestIn,
  TellerSession,
  TillAvailability,
} from "@/lib/api/types";

const ts = (sid: string) => `/api/s/${sid}/teller-sessions`;

export const STATUS_LABEL: Record<string, string> = {
  pending_open: "Waiting for opening approval",
  open: "Open",
  closing: "Waiting for closing approval",
  closed: "Closed",
  cancelled: "Request cancelled",
};

export const useTillAvailability = (sid: string, enabled = true) =>
  useQuery({
    queryKey: ["tills-availability", sid],
    queryFn: () => apiFetch<TillAvailability[]>(`/api/s/${sid}/tills`),
    enabled,
  });

export const useMyTellerSession = (sid: string, enabled = true) =>
  useQuery({
    queryKey: ["teller-session-me", sid],
    queryFn: () => apiFetch<TellerSession | null>(`${ts(sid)}/me`),
    enabled,
    refetchInterval: 15000,
  });

export const useTellerSessions = (sid: string, enabled = true) =>
  useQuery({
    queryKey: ["teller-sessions", sid],
    queryFn: () => apiFetch<TellerSession[]>(ts(sid)),
    enabled,
    refetchInterval: 15000,
  });

export const useDenominations = () =>
  useQuery({
    queryKey: ["denominations"],
    queryFn: () => apiFetch<DenominationOut[]>("/api/denominations"),
    staleTime: Infinity,
  });

type Action =
  | { kind: "open-request"; body: OpenRequestIn }
  | { kind: "cancel"; id: string }
  | { kind: "approve-open"; id: string }
  | { kind: "reject-open"; id: string; reason: string }
  | { kind: "close-count"; id: string; body: CloseCountIn }
  | { kind: "approve-close"; id: string }
  | { kind: "reject-close"; id: string; reason: string };

/** One mutation for every teller-session action; refreshes everything it touches. */
export function useTellerAction(sid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (a: Action) => {
      const post = (path: string, json?: unknown) =>
        apiFetch<TellerSession>(`${ts(sid)}/${path}`, { method: "POST", json });
      switch (a.kind) {
        case "open-request":
          return post("open-request", a.body);
        case "cancel":
          return post(`${a.id}/cancel`);
        case "approve-open":
          return post(`${a.id}/approve-open`);
        case "reject-open":
          return post(`${a.id}/reject-open`, { reason: a.reason });
        case "close-count":
          return post(`${a.id}/close-count`, a.body);
        case "approve-close":
          return post(`${a.id}/approve-close`);
        case "reject-close":
          return post(`${a.id}/reject-close`, { reason: a.reason });
      }
    },
    onSuccess: () => {
      for (const k of [
        "teller-session-me",
        "teller-sessions",
        "tills-availability",
        "cash-transfers",
        "vault",
      ])
        qc.invalidateQueries({ queryKey: [k, sid] });
    },
  });
}
