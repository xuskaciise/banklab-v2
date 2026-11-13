"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiFetch } from "@/lib/api/client";
import type {
  ChangePasswordRequest,
  LoginResponse,
  Me,
  StaffLoginRequest,
  StudentLoginRequest,
} from "@/lib/api/types";

export const ME_KEY = ["me"] as const;

export function useMe() {
  return useQuery<Me | null>({
    queryKey: ME_KEY,
    queryFn: async () => {
      try {
        return await apiFetch<Me>("/api/auth/me");
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return null;
        throw e;
      }
    },
    retry: false,
  });
}

function useLoginMutation<T>(path: string) {
  const qc = useQueryClient();
  return useMutation({
    // Login rotates the CSRF token; apiFetch re-reads the cookie on every
    // unsafe call, so the next POST automatically uses the new token.
    mutationFn: (body: T) =>
      apiFetch<LoginResponse>(path, { method: "POST", json: body }),
    onSuccess: (data) => qc.setQueryData(ME_KEY, data.user),
  });
}

export function useStaffLogin() {
  return useLoginMutation<StaffLoginRequest>("/api/auth/staff-login");
}

export function useStudentLogin() {
  return useLoginMutation<StudentLoginRequest>("/api/auth/student-login");
}

/** Maps login errors to user-facing text (401 generic, 429 throttle). */
export function loginErrorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 401) return "Invalid credentials";
    if (e.status === 429) return "Too many attempts, try again in a few minutes";
  }
  return e instanceof Error ? e.message : "Login failed";
}

export function isStudent(user: Me | null | undefined): boolean {
  return user?.platform_role === "student";
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch<void>("/api/auth/logout", { method: "POST" }),
    onSettled: () => {
      qc.clear();
      qc.setQueryData(ME_KEY, null);
    },
  });
}

export function useChangePassword() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ChangePasswordRequest) =>
      apiFetch<Me>("/api/auth/change-password", { method: "POST", json: body }),
    onSuccess: (me) => qc.setQueryData(ME_KEY, me),
  });
}
