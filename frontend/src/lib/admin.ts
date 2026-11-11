"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiBlob, apiFetch } from "@/lib/api/client";
import { ME_KEY } from "@/lib/auth";
import type {
  ClassOut,
  CoaLineIn,
  CoaLineOut,
  CoaLinePatch,
  CoaTemplateDetail,
  CoaTemplateRow,
  InstitutionOut,
  InstructorIn,
  InstructorOut,
  SessionTemplateIn,
  SessionTemplateOut,
} from "@/lib/api/types";

const A = "/api/admin";
const INSTRUCTORS = ["admin", "instructors"] as const;
const INSTITUTION = ["admin", "institution"] as const;
const COA = ["admin", "coa"] as const;
const SESSION_TPL = ["admin", "session-templates"] as const;

// ---- instructors ----
export const useInstructors = (enabled = true) =>
  useQuery({
    queryKey: INSTRUCTORS,
    enabled,
    queryFn: () => apiFetch<InstructorOut[]>(`${A}/instructors`),
  });

export function useCreateInstructor() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: InstructorIn) =>
      apiFetch<InstructorOut>(`${A}/instructors`, { method: "POST", json: body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: INSTRUCTORS }),
  });
}

export function useSetInstructorActive() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { id: string; is_active: boolean }) =>
      apiFetch<InstructorOut>(`${A}/instructors/${v.id}/active`, {
        method: "PUT",
        json: { is_active: v.is_active },
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: INSTRUCTORS }),
  });
}

export function useSetClassInstructor(classId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (instructor_id: string) =>
      apiFetch<ClassOut>(`${A}/classes/${classId}/instructor`, {
        method: "PUT",
        json: { instructor_id },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["class", classId] });
      qc.invalidateQueries({ queryKey: ["classes"] });
    },
  });
}

export const useResetInstructorPassword = () =>
  useMutation({
    mutationFn: (id: string) =>
      apiFetch<void>(`${A}/instructors/${id}/reset-password`, { method: "POST" }),
  });

// ---- institution ----
export const useAdminInstitution = () =>
  useQuery({
    queryKey: INSTITUTION,
    queryFn: () => apiFetch<InstitutionOut>(`${A}/institution`),
  });

function useInstitutionWrite<V = void>(fn: (v: V) => Promise<InstitutionOut>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (data) => {
      qc.setQueryData(INSTITUTION, data);
      qc.invalidateQueries({ queryKey: ME_KEY });
      qc.invalidateQueries({ queryKey: ["institution-logo"] });
    },
  });
}

export const useUpdateInstitutionName = () =>
  useInstitutionWrite((name: string) =>
    apiFetch<InstitutionOut>(`${A}/institution`, { method: "PUT", json: { name } }),
  );

export const useUploadLogo = () =>
  useInstitutionWrite((file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiFetch<InstitutionOut>(`${A}/institution/logo`, { method: "POST", form });
  });

export const useRemoveLogo = () =>
  useInstitutionWrite(() =>
    apiFetch<InstitutionOut>(`${A}/institution/logo`, { method: "DELETE" }),
  );

/** Object URL of the institution logo (null when none). Session-cookie protected, so fetched as a blob. */
export function useLogoSrc(logoUrl?: string | null) {
  return useQuery({
    queryKey: ["institution-logo", logoUrl ?? null],
    enabled: !!logoUrl,
    staleTime: 10 * 60 * 1000,
    queryFn: async () =>
      URL.createObjectURL(await apiBlob(logoUrl as string, { cache: "no-store" })),
  }).data ?? null;
}

// ---- CoA templates ----
export const useCoaTemplates = () =>
  useQuery({
    queryKey: COA,
    queryFn: () => apiFetch<CoaTemplateRow[]>(`${A}/coa-templates`),
  });

export const useCoaTemplate = (id: string) =>
  useQuery({
    queryKey: [...COA, id],
    queryFn: () => apiFetch<CoaTemplateDetail>(`${A}/coa-templates/${id}`),
  });

export function useCreateCoaTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; copy_from_id?: string | null }) =>
      apiFetch<CoaTemplateDetail>(`${A}/coa-templates`, { method: "POST", json: body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: COA }),
  });
}

export function useDeleteCoaTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<void>(`${A}/coa-templates/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: COA }),
  });
}

export function useAddCoaLine(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CoaLineIn) =>
      apiFetch<CoaLineOut>(`${A}/coa-templates/${id}/lines`, { method: "POST", json: body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: COA }),
  });
}

export function useUpdateCoaLine(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { lineId: string; patch: CoaLinePatch }) =>
      apiFetch<CoaLineOut>(`${A}/coa-templates/${id}/lines/${v.lineId}`, {
        method: "PATCH",
        json: v.patch,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: COA }),
  });
}

// ---- session templates ----
export const useAdminSessionTemplates = () =>
  useQuery({
    queryKey: SESSION_TPL,
    queryFn: () => apiFetch<SessionTemplateOut[]>(`${A}/session-templates`),
  });

export function useSaveSessionTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { id?: string; body: SessionTemplateIn }) =>
      v.id
        ? apiFetch<SessionTemplateOut>(`${A}/session-templates/${v.id}`, {
            method: "PUT",
            json: v.body,
          })
        : apiFetch<SessionTemplateOut>(`${A}/session-templates`, {
            method: "POST",
            json: v.body,
          }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SESSION_TPL });
      qc.invalidateQueries({ queryKey: ["templates"] });
    },
  });
}

export function useDeleteSessionTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<void>(`${A}/session-templates/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SESSION_TPL });
      qc.invalidateQueries({ queryKey: ["templates"] });
    },
  });
}
