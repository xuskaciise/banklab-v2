"use client";

import { AlertTriangle, CheckCircle2, Landmark, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatMoney } from "@/lib/banking";
import { nonZeroCurrencies, useCurrencies } from "@/lib/platform";
import type { VaultOut } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

export function VaultHeader({
  vault,
  updatedAt,
  fetching,
  onRefresh,
}: {
  vault?: VaultOut;
  updatedAt: number;
  fetching: boolean;
  onRefresh: () => void;
}) {
  const time = updatedAt
    ? new Date(updatedAt).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })
    : "--:--";
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-xl font-semibold tracking-tight text-text-strong sm:text-2xl">Vault</h1>
        <p className="mt-0.5 text-sm text-text-muted">
          Branch cash positions, reconciliation with the general ledger and dual-control cash transfers.
        </p>
        {vault && vault.branches.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {vault.branches.map((b) => (
              <span
                key={b.branch_id}
                className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-2.5 py-0.5 text-xs font-medium text-text-body"
              >
                <Landmark className="size-3.5 text-bank-primary" aria-hidden />
                {b.branch_name} · {b.branch_code}
              </span>
            ))}
          </div>
        )}
      </div>
      <div className="flex items-center gap-2 text-xs text-text-muted">
        <span>Last updated {time}</span>
        <Button
          variant="outline"
          size="icon"
          aria-label="Refresh vault data"
          onClick={onRefresh}
          disabled={fetching}
          className="size-9"
        >
          <RefreshCw className={cn("size-4", fetching && "animate-spin")} aria-hidden />
        </Button>
      </div>
    </div>
  );
}

const TINT: Record<string, string> = {
  USD: "border-l-bank-primary",
  SOS: "border-l-bank-accent",
};

/** Vault cash per branch and currency; amounts are server positions. */
export function VaultCash({ vault, loading }: { vault?: VaultOut; loading: boolean }) {
  const currencies = useCurrencies(
    (vault?.branches ?? []).flatMap((b) => nonZeroCurrencies(b.positions)),
  );
  if (loading)
    return (
      <div className="grid gap-3 sm:grid-cols-2">
        <Skeleton className="h-24 rounded-xl" />
        <Skeleton className="h-24 rounded-xl" />
      </div>
    );
  return (
    <div className="space-y-3">
      {vault?.branches.map((b) => (
        <div key={b.branch_id} className="grid grid-cols-[repeat(auto-fit,minmax(260px,1fr))] gap-3">
          {currencies.map((c) => {
            const pos = b.positions.find((p) => p.currency === c);
            const full = formatMoney(pos?.balance ?? "0", c);
            return (
              <div
                key={c}
                className={cn(
                  "min-w-0 rounded-xl border border-l-4 border-border bg-card p-4 shadow-xs",
                  TINT[c],
                )}
              >
                <div className="flex items-center gap-2 text-xs font-medium tracking-wide text-text-muted uppercase">
                  <Landmark className="size-4 text-bank-primary" aria-hidden />
                  Vault cash {c}
                  {(vault?.branches.length ?? 0) > 1 && (
                    <span className="normal-case">· {b.branch_code}</span>
                  )}
                </div>
                <p
                  title={full}
                  className="mt-2 flex min-w-0 items-baseline gap-1.5 text-2xl font-semibold whitespace-nowrap text-text-strong tabular-nums sm:text-3xl"
                >
                  <span className="shrink-0 text-sm font-medium text-text-muted">{c}</span>
                  <span className="truncate">{full.slice(c.length).trim()}</span>
                </p>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

/** One compact reconciliation table from the server's reconciliation rows. */
export function ReconCard({ vault }: { vault?: VaultOut }) {
  const rows = vault?.reconciliation ?? [];
  if (!rows.length) return null;
  return (
    <>
      <section className="rounded-xl border border-border bg-card p-4 shadow-xs">
        <h2 className="mb-2 text-sm font-semibold text-text-strong">
          GL reconciliation <span className="text-xs font-normal text-text-muted">(whole bank)</span>
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="text-left text-xs text-text-muted">
                {["Currency", "Vaults", "GL", "Tills", "GL", "Difference", "Status"].map((h, i) => (
                  <th key={i} className={cn("pb-2 font-medium", i > 0 && i < 6 && "text-right", i === 6 && "pl-4")}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map((r) => (
                <tr key={r.currency}>
                  <td className="py-2 font-semibold text-text-strong">{r.currency}</td>
                  {[r.vault_total, r.gl_vault, r.teller_total, r.gl_teller].map((v, i) => (
                    <td key={i} className="py-2 text-right whitespace-nowrap tabular-nums">
                      {formatMoney(v, r.currency)}
                    </td>
                  ))}
                  <td className={cn("py-2 text-right whitespace-nowrap tabular-nums", r.ok ? "text-text-muted" : "font-semibold text-fin-danger")}>
                    {r.ok ? "0.00" : "Mismatch"}
                  </td>
                  <td className="py-2 pl-4">
                    {r.ok ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-fin-success-bg px-2 py-0.5 text-xs font-medium text-fin-success-dark">
                        <CheckCircle2 className="size-3" aria-hidden />
                        Reconciled
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-full bg-fin-danger-bg px-2 py-0.5 text-xs font-medium text-fin-danger">
                        <AlertTriangle className="size-3" aria-hidden />
                        Out of balance
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

/** Banner shown at the top when any reconciliation row is out of balance. */
export function ReconAlert({ vault }: { vault?: VaultOut }) {
  if (!vault?.reconciliation.some((r) => !r.ok)) return null;
  return (
    <div role="alert" className="flex items-center gap-2 rounded-xl border border-fin-danger/30 bg-fin-danger-bg px-4 py-2.5 text-sm font-medium text-fin-danger">
      <AlertTriangle className="size-4 shrink-0" aria-hidden />
      The vault or till cash does not match the general ledger. Check the reconciliation below.
    </div>
  );
}
