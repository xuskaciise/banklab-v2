"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import type {
  Learning,
  SessionDashboard,
  SessionOut,
  StaffDashboard,
} from "@/lib/api/types";

/** Role dashboard for the signed-in student; numbers come from the server. */
export const useSessionDashboard = (sid: string) =>
  useQuery({
    queryKey: ["dashboard", sid],
    queryFn: () => apiFetch<SessionDashboard>(`/api/s/${sid}/dashboard`),
    enabled: !!sid,
  });

export const useStaffDashboard = () =>
  useQuery({
    queryKey: ["staff-dashboard"],
    queryFn: () => apiFetch<StaffDashboard>("/api/dashboard"),
  });

export const useLearning = (sid: string, txnId: string | null) =>
  useQuery({
    queryKey: ["learning", sid, txnId],
    queryFn: () => apiFetch<Learning>(`/api/s/${sid}/transactions/${txnId}/learning`),
    enabled: !!txnId,
    retry: false,
  });

export function useSetLearningPanel(sessionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (enabled: boolean) =>
      apiFetch<SessionOut>(`/api/sessions/${sessionId}/learning-panel`, {
        method: "POST",
        json: { enabled },
      }),
    onSuccess: (s) => {
      for (const key of [
        ["session", sessionId],
        ["class-sessions", s.class_id],
        ["session-me", sessionId],
        ["staff-dashboard"],
        ["my-sessions"],
      ])
        qc.invalidateQueries({ queryKey: key });
    },
  });
}
