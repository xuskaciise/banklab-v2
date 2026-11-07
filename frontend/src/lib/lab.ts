"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
  type QueryKey,
} from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import type {
  AddMembersIn,
  AddStudentIn,
  BankOut,
  BusinessDayOut,
  ClassIn,
  ClassOut,
  CsvResult,
  MemberOut,
  MySession,
  OverrideIn,
  PagedAudit,
  PermissionCell,
  SessionIn,
  SessionMe,
  SessionOut,
  StudentOut,
  TemplateOut,
  UpdateStudentIn,
} from "@/lib/api/types";

export const BANK_ROLES = [
  "teller",
  "cso",
  "manager",
  "vault_custodian",
  "accountant",
] as const;

export const ROLE_LABEL: Record<string, string> = {
  teller: "Teller",
  cso: "Customer Service Officer",
  manager: "Supervisor / Manager",
  vault_custodian: "Vault Custodian",
  accountant: "Accountant",
};

export const roleLabel = (r?: string | null) =>
  r ? (ROLE_LABEL[r] ?? r) : "No role";

export function formatDateTime(iso?: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

const j = (method: string, json?: unknown) => ({ method, json });

/** Mutation that invalidates the given query keys on success. */
function useApiMutation<V, R>(
  fn: (v: V) => Promise<R>,
  invalidate: (v: V, r: R) => QueryKey[],
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (r, v) => {
      for (const key of invalidate(v, r))
        qc.invalidateQueries({ queryKey: key });
    },
  });
}

// ---- classes ----
export const useClasses = () =>
  useQuery({
    queryKey: ["classes"],
    queryFn: () => apiFetch<ClassOut[]>("/api/classes"),
  });
export const useClass = (id: string) =>
  useQuery({
    queryKey: ["class", id],
    queryFn: () => apiFetch<ClassOut>(`/api/classes/${id}`),
  });
export const useCreateClass = () =>
  useApiMutation(
    (b: ClassIn) => apiFetch<ClassOut>("/api/classes", j("POST", b)),
    () => [["classes"]],
  );

// ---- students ----
export const useStudents = (classId: string) =>
  useQuery({
    queryKey: ["students", classId],
    queryFn: () => apiFetch<StudentOut[]>(`/api/classes/${classId}/students`),
  });
export const useAddStudent = (classId: string) =>
  useApiMutation(
    (b: AddStudentIn) =>
      apiFetch<{ student: StudentOut; created: boolean }>(
        `/api/classes/${classId}/students`,
        j("POST", b),
      ),
    () => [["students", classId]],
  );
export const useUpdateStudent = (classId: string) =>
  useApiMutation(
    (v: { userId: string; body: UpdateStudentIn }) =>
      apiFetch<StudentOut>(
        `/api/classes/${classId}/students/${v.userId}`,
        j("PATCH", v.body),
      ),
    () => [["students", classId]],
  );
export const useResetStudentPassword = (classId: string) =>
  useApiMutation(
    (userId: string) =>
      apiFetch<void>(`/api/auth/users/${userId}/reset-password`, j("POST")),
    () => [["students", classId]],
  );
export const useCsvPreview = (classId: string) =>
  useMutation({
    mutationFn: (csv_text: string) =>
      apiFetch<CsvResult>(
        `/api/classes/${classId}/students/import/preview`,
        j("POST", { csv_text }),
      ),
  });
export const useCsvConfirm = (classId: string) =>
  useApiMutation(
    (csv_text: string) =>
      apiFetch<CsvResult>(
        `/api/classes/${classId}/students/import/confirm`,
        j("POST", { csv_text }),
      ),
    () => [["students", classId]],
  );

// ---- templates ----
export const useTemplates = (classId?: string) =>
  useQuery({
    queryKey: ["templates", classId ?? null],
    queryFn: () =>
      apiFetch<TemplateOut[]>(
        `/api/templates${classId ? `?class_id=${classId}` : ""}`,
      ),
  });

// ---- sessions ----
export const useClassSessions = (classId: string) =>
  useQuery({
    queryKey: ["class-sessions", classId],
    queryFn: () => apiFetch<SessionOut[]>(`/api/classes/${classId}/sessions`),
  });
export const useSession = (id: string) =>
  useQuery({
    queryKey: ["session", id],
    queryFn: () => apiFetch<SessionOut>(`/api/sessions/${id}`),
  });
export const useCreateSession = () =>
  useApiMutation(
    (b: SessionIn) => apiFetch<SessionOut>("/api/sessions", j("POST", b)),
    (_, s) => [["class-sessions", s.class_id]],
  );

type Transition = "open" | "archive" | "reopen";
export const useSessionTransition = (sessionId: string) =>
  useApiMutation(
    (v: { action: Transition; group_count?: number }) =>
      apiFetch<SessionOut>(
        `/api/sessions/${sessionId}/${v.action}`,
        j(
          "POST",
          v.action === "open" ? { group_count: v.group_count ?? null } : undefined,
        ),
      ),
    (_, s) => [
      ["session", sessionId],
      ["class-sessions", s.class_id],
      ["banks", sessionId],
      ["members", sessionId],
      ["bdays", sessionId],
      ["my-sessions"],
    ],
  );

export const useBanks = (sessionId: string) =>
  useQuery({
    queryKey: ["banks", sessionId],
    queryFn: () => apiFetch<BankOut[]>(`/api/sessions/${sessionId}/banks`),
  });
export const useAddBank = (sessionId: string) =>
  useApiMutation(
    () =>
      apiFetch<BankOut>(`/api/sessions/${sessionId}/banks`, j("POST")),
    () => [["banks", sessionId], ["bdays", sessionId]],
  );
export const useBusinessDays = (sessionId: string) =>
  useQuery({
    queryKey: ["bdays", sessionId],
    queryFn: () =>
      apiFetch<BusinessDayOut[]>(`/api/sessions/${sessionId}/business-days`),
  });

// ---- members ----
export const useMembers = (sessionId: string) =>
  useQuery({
    queryKey: ["members", sessionId],
    queryFn: () => apiFetch<MemberOut[]>(`/api/sessions/${sessionId}/members`),
  });
export const useAddMembers = (sessionId: string) =>
  useApiMutation(
    (b: AddMembersIn) =>
      apiFetch<MemberOut[]>(`/api/sessions/${sessionId}/members`, j("POST", b)),
    () => [["members", sessionId]],
  );
export const useMoveMember = (sessionId: string) =>
  useApiMutation(
    (v: { memberId: string; bank_id: string }) =>
      apiFetch<MemberOut>(
        `/api/sessions/${sessionId}/members/${v.memberId}/bank`,
        j("POST", { bank_id: v.bank_id }),
      ),
    () => [["members", sessionId]],
  );
export const useMemberVisibility = (sessionId: string) =>
  useApiMutation(
    (v: { memberId: string; visibility: string | null }) =>
      apiFetch<MemberOut>(
        `/api/sessions/${sessionId}/members/${v.memberId}/visibility`,
        j("POST", { visibility: v.visibility }),
      ),
    () => [["members", sessionId]],
  );
export const useAssignRole = (sessionId: string) =>
  useApiMutation(
    (v: { memberId: string; role: string }) =>
      apiFetch<unknown>(
        `/api/sessions/${sessionId}/members/${v.memberId}/role`,
        j("POST", { role: v.role }),
      ),
    () => [["members", sessionId], ["audit", sessionId]],
  );

// ---- permissions ----
export const usePermissionMatrix = (sessionId: string) =>
  useQuery({
    queryKey: ["perms", sessionId],
    queryFn: () =>
      apiFetch<PermissionCell[]>(`/api/sessions/${sessionId}/permissions`),
  });
export const useSetOverride = (sessionId: string) =>
  useApiMutation(
    (b: OverrideIn) =>
      apiFetch<unknown>(
        `/api/sessions/${sessionId}/permissions/overrides`,
        j("PUT", b),
      ),
    () => [["perms", sessionId], ["audit", sessionId]],
  );
export const useClearOverride = (sessionId: string) =>
  useApiMutation(
    (b: { role: string; permission_code: string }) =>
      apiFetch<void>(
        `/api/sessions/${sessionId}/permissions/overrides/clear`,
        j("POST", b),
      ),
    () => [["perms", sessionId], ["audit", sessionId]],
  );

// ---- audit ----
export const useAudit = (sessionId: string, page: number, action: string) =>
  useQuery({
    queryKey: ["audit", sessionId, page, action],
    queryFn: () => {
      const q = new URLSearchParams({
        session_id: sessionId,
        page: String(page),
      });
      if (action) q.set("action", action);
      return apiFetch<PagedAudit>(`/api/audit?${q}`);
    },
  });

// ---- student ----
export const useMySessions = () =>
  useQuery({
    queryKey: ["my-sessions"],
    queryFn: () => apiFetch<MySession[]>("/api/my/sessions"),
  });
export const useSessionMe = (sessionId: string) =>
  useQuery({
    queryKey: ["session-me", sessionId],
    queryFn: () => apiFetch<SessionMe>(`/api/s/${sessionId}/me`),
  });
