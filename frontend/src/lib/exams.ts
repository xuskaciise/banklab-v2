"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiBlob, apiFetch } from "@/lib/api/client";
import type {
  CheckType,
  ExamIn,
  ExamOut,
  ExamResults,
  ExamTaskIn,
  ExamTaskPatch,
  MyExamResult,
  StudentExam,
} from "@/lib/api/types";

export const PRODUCT_CODES = ["SAV-USD", "SAV-SOS", "CUR-USD", "CUR-SOS"] as const;

/** Plain points (not money): drop trailing zeros. */
export function fmtPoints(v: number | string | null | undefined) {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  return Number.isFinite(n) ? String(Number(n.toFixed(2))) : String(v);
}

/** datetime-local value (local time) -> ISO string with timezone. */
export function localToIso(v: string) {
  return new Date(v).toISOString();
}
/** ISO -> datetime-local value in the browser's timezone. */
export function isoToLocal(iso: string) {
  const d = new Date(iso);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

export function fmtCountdown(total: number) {
  const s = Math.max(0, Math.floor(total));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(s % 60)}` : `${pad(m)}:${pad(s % 60)}`;
}

const base = (sid: string) => `/api/sessions/${sid}/exam`;
const sBase = (sid: string) => `/api/s/${sid}/exam`;

// ---- instructor ----
export const useCheckTypes = () =>
  useQuery({
    queryKey: ["exam-check-types"],
    queryFn: () => apiFetch<CheckType[]>("/api/exam-check-types"),
    staleTime: Infinity,
  });

export const useExam = (sid: string) =>
  useQuery({
    queryKey: ["exam", sid],
    queryFn: () => apiFetch<ExamOut | null>(base(sid)),
    enabled: !!sid,
  });

/** Mutation whose ExamOut result replaces the cached exam. */
function useExamMutation<V>(sid: string, fn: (v: V) => Promise<ExamOut>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (exam) => qc.setQueryData(["exam", sid], exam),
  });
}

export const useSaveExam = (sid: string) =>
  useExamMutation(sid, (json: ExamIn) =>
    apiFetch<ExamOut>(base(sid), { method: "PUT", json }),
  );
export const useCreateTask = (sid: string) =>
  useExamMutation(sid, (json: ExamTaskIn) =>
    apiFetch<ExamOut>(`${base(sid)}/tasks`, { method: "POST", json }),
  );
export const useUpdateTask = (sid: string) =>
  useExamMutation(sid, (v: { id: string; patch: ExamTaskPatch }) =>
    apiFetch<ExamOut>(`${base(sid)}/tasks/${v.id}`, { method: "PUT", json: v.patch }),
  );
export const useDeleteTask = (sid: string) =>
  useExamMutation(sid, (id: string) =>
    apiFetch<ExamOut>(`${base(sid)}/tasks/${id}`, { method: "DELETE" }),
  );
export const useReorderTasks = (sid: string) =>
  useExamMutation(sid, (task_ids: string[]) =>
    apiFetch<ExamOut>(`${base(sid)}/tasks/reorder`, { method: "POST", json: { task_ids } }),
  );
export const usePublishExam = (sid: string) =>
  useExamMutation(sid, () => apiFetch<ExamOut>(`${base(sid)}/publish`, { method: "POST" }));

export const useExamResults = (sid: string) =>
  useQuery({
    queryKey: ["exam-results", sid],
    queryFn: () => apiFetch<ExamResults>(`${base(sid)}/results`),
    enabled: !!sid,
    refetchInterval: 30_000,
  });

function useResultsMutation<V>(sid: string, fn: (v: V) => Promise<ExamResults>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (r) => qc.setQueryData(["exam-results", sid], r),
  });
}
export const useAdjustResult = (sid: string) =>
  useResultsMutation(sid, (v: { resultId: string; points: number | null }) =>
    apiFetch<ExamResults>(`${base(sid)}/results/${v.resultId}/adjust`, {
      method: "POST",
      json: { adjusted_points: v.points },
    }),
  );
export const usePublishResults = (sid: string) =>
  useResultsMutation(sid, () =>
    apiFetch<ExamResults>(`${base(sid)}/results/publish`, { method: "POST" }),
  );

export async function downloadExamResults(sid: string, ext: "pdf" | "xlsx") {
  const win = ext === "pdf" ? window.open("", "_blank") : null;
  try {
    const blob = await apiBlob(`${base(sid)}/results.${ext}`);
    const href = URL.createObjectURL(blob);
    if (ext === "pdf") {
      if (win) win.location.href = href;
      else window.location.href = href;
    } else {
      const a = document.createElement("a");
      a.href = href;
      a.download = "exam-results.xlsx";
      document.body.appendChild(a);
      a.click();
      a.remove();
    }
    setTimeout(() => URL.revokeObjectURL(href), 60_000);
  } catch (e) {
    win?.close();
    throw e;
  }
}

// ---- student ----
export const useStudentExam = (sid: string) =>
  useQuery({
    queryKey: ["student-exam", sid],
    queryFn: () => apiFetch<StudentExam>(sBase(sid)),
    enabled: !!sid,
  });

function useStudentExamMutation(sid: string, path: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch<StudentExam>(`${sBase(sid)}/${path}`, { method: "POST" }),
    onSuccess: (e) => {
      qc.setQueryData(["student-exam", sid], e);
      qc.invalidateQueries({ queryKey: ["session-me", sid] });
    },
  });
}
export const useStartExam = (sid: string) => useStudentExamMutation(sid, "start");
export const useSubmitExam = (sid: string) => useStudentExamMutation(sid, "submit");

export const useMyExamResult = (sid: string, enabled: boolean) =>
  useQuery({
    queryKey: ["student-exam-result", sid],
    queryFn: () => apiFetch<MyExamResult>(`${sBase(sid)}/result`),
    enabled: !!sid && enabled,
    retry: false,
  });

/**
 * Seconds left, seeded from the server's remaining_seconds and ticked locally.
 * Calls onZero once when it reaches 0.
 */
export function useCountdown(
  remaining: number | null | undefined,
  onZero?: () => void,
) {
  const [left, setLeft] = useState<number | null>(remaining ?? null);
  const [prev, setPrev] = useState(remaining);
  const zeroCb = useRef(onZero);
  useEffect(() => {
    zeroCb.current = onZero;
  });
  if (prev !== remaining) {
    setPrev(remaining);
    setLeft(remaining ?? null);
  }
  const active = remaining !== null && remaining !== undefined;
  useEffect(() => {
    if (!active) return;
    const end = Date.now() + (remaining as number) * 1000;
    let fired = false;
    const tick = () => {
      const s = Math.max(0, Math.ceil((end - Date.now()) / 1000));
      setLeft(s);
      if (s === 0 && !fired) {
        fired = true;
        zeroCb.current?.();
      }
    };
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, [active, remaining]);
  return left;
}
