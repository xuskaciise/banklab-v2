"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import type { PlatformSettings, PlatformSettingsIn } from "@/lib/api/types";

export const PLATFORM_KEY = ["platform-settings"] as const;
const FALLBACK = ["USD"];
/** Canonical display order for currencies. */
const ORDER = ["USD", "SOS"];

export function usePlatformSettings() {
  return useQuery<PlatformSettings>({
    queryKey: PLATFORM_KEY,
    queryFn: () => apiFetch<PlatformSettings>("/api/platform/settings"),
    staleTime: 10 * 60 * 1000,
  });
}

/**
 * Currencies the platform currently allows for NEW activity (forms, pickers).
 * Pass `held` (currencies of existing balances/records) to also keep those
 * visible so history stays readable; falsy entries are ignored.
 */
export function useCurrencies(held: Iterable<string | null | undefined> = []): string[] {
  const enabled = usePlatformSettings().data?.currencies ?? FALLBACK;
  const set = new Set(enabled);
  for (const c of held) if (c) set.add(c);
  return [...set].sort(
    (a, b) =>
      (ORDER.indexOf(a) === -1 ? 99 : ORDER.indexOf(a)) -
      (ORDER.indexOf(b) === -1 ? 99 : ORDER.indexOf(b)),
  );
}

/** True when SOS may be used for new activity. */
export function useSosEnabled(): boolean {
  return usePlatformSettings().data?.sos_enabled ?? false;
}

export function useUpdatePlatformSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: PlatformSettingsIn) =>
      apiFetch<PlatformSettings>("/api/platform/settings", { method: "PUT", json: body }),
    onSuccess: (data) => {
      qc.setQueryData(PLATFORM_KEY, data);
      // Balances, reports and forms depend on the enabled currencies.
      qc.invalidateQueries();
    },
  });
}

/** Currencies of balances that hold money (so a non-zero SOS balance stays visible). */
export const nonZeroCurrencies = (rows: { currency: string; balance: number | string }[]) =>
  rows.filter((r) => Number(r.balance) !== 0).map((r) => r.currency);
