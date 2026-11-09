"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import type { EodClose, EodStatus } from "@/lib/api/types";

export const useEodStatus = (sid: string, enabled = true) =>
  useQuery({
    queryKey: ["eod", sid],
    queryFn: () => apiFetch<EodStatus>(`/api/s/${sid}/eod`),
    enabled,
  });

export function useCloseDay(sid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch<EodClose>(`/api/s/${sid}/eod/close`, { method: "POST" }),
    // Success or 409: re-read everything (status, business date, tellers, vault).
    onSettled: () => {
      qc.invalidateQueries();
    },
  });
}

/** Label helper: the day after an ISO date (calendar arithmetic only). */
export function nextDate(iso: string) {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
}
