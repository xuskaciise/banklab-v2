"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiFetch } from "@/lib/api/client";
import type {
  ChangePasswordRequest,
  LoginRequest,
  LoginResponse,
  Me,
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

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    // Login rotates the CSRF token; apiFetch re-reads the cookie on every
    // unsafe call, so the next POST automatically uses the new token.
    mutationFn: (body: LoginRequest) =>
      apiFetch<LoginResponse>("/api/auth/login", { method: "POST", json: body }),
    onSuccess: (data) => qc.setQueryData(ME_KEY, data.user),
  });
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
