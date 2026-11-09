"use client";

import { Info, Loader2, Send } from "lucide-react";
import type { TillAvailability } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FormSection } from "@/components/shared/form-layout";
import { StatusBadge } from "@/components/shared/status-badge";
import { ErrorMsg } from "@/components/lab/common";
import { FieldLabel } from "@/components/transactions/field-label";
import { CURRENCIES } from "./session-bits";

/** Float is optional; every filled value must be a number >= 0. */
export function floatsValid(floats: Record<string, string>) {
  return CURRENCIES.every((c) => {
    const raw = (floats[c] ?? "").trim();
    if (!raw) return true;
    const n = Number(raw);
    return Number.isFinite(n) && n >= 0;
  });
}

/** Selected-till summary shown under the combobox. */
export function TillSummary({ till }: { till: TillAvailability | undefined }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      {till ? (
        <dl className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <dt className="text-xs text-text-muted">Till</dt>
            <dd className="font-mono font-semibold text-text-strong">{till.code}</dd>
          </div>
          <div>
            <dt className="text-xs text-text-muted">Status</dt>
            <dd>
              <StatusBadge status="open" label="Free" />
            </dd>
          </div>
          <div className="col-span-2">
            <dt className="text-xs text-text-muted">Branch</dt>
            <dd className="text-text-strong">
              {till.branch_name}{" "}
              <span className="text-xs text-text-muted">{till.branch_code}</span>
            </dd>
          </div>
          <div className="col-span-2">
            <dt className="text-xs text-text-muted">Location</dt>
            <dd className={till.branch_address ? "text-text-body" : "text-text-muted"}>
              {till.branch_address || "No address"}
            </dd>
          </div>
        </dl>
      ) : (
        <p className="rounded-lg bg-surface p-4 text-center text-sm text-text-muted">
          Choose a free till from the list.
        </p>
      )}
    </div>
  );
}

/** Opening float, notice and submit. */
export function OpenTillForm({
  till,
  floats,
  onFloats,
  err,
  pending,
}: {
  till: TillAvailability | undefined;
  floats: Record<string, string>;
  onFloats: (f: Record<string, string>) => void;
  err: string | null;
  pending: boolean;
}) {
  const valid = floatsValid(floats);
  return (
    <div className="space-y-4">
      <FormSection title="Opening Cash Float">
        {CURRENCIES.map((c) => (
          <div key={c} className="space-y-1.5">
            <FieldLabel htmlFor={`float-${c}`} optional>
              {c} float
            </FieldLabel>
            <div className="flex h-14 items-center gap-3 rounded-lg border border-border bg-card px-3 transition-colors focus-within:border-bank-accent focus-within:ring-2 focus-within:ring-bank-accent/40 hover:border-text-muted">
              <span className="rounded-md border border-border bg-surface px-2.5 py-1 text-sm font-semibold text-text-strong">
                {c}
              </span>
              <Input
                id={`float-${c}`}
                inputMode="decimal"
                placeholder="0.00"
                value={floats[c] ?? ""}
                aria-invalid={
                  !!(floats[c] ?? "").trim() && !floatsValid({ [c]: floats[c] ?? "" })
                }
                onChange={(e) => onFloats({ ...floats, [c]: e.target.value })}
                className="h-full flex-1 rounded-none border-0 bg-transparent px-0 text-right text-xl font-semibold tabular-nums shadow-none hover:border-0 focus-visible:ring-0"
              />
            </div>
          </div>
        ))}
        {!valid && (
          <p role="alert" className="text-sm text-fin-danger">
            Enter a number of 0 or more.
          </p>
        )}
        <p className="flex gap-2 rounded-lg bg-bank-sky-light p-3 text-sm text-bank-primary">
          <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
          An opening cash float is requested from the vault and requires manager
          approval before the till becomes operational.
        </p>
      </FormSection>

      {err && <ErrorMsg error={new Error(err)} />}
      <Button
        type="submit"
        size="lg"
        className="w-full"
        disabled={pending || !till || !till.available || !valid}
      >
        {pending ? <Loader2 className="animate-spin" /> : <Send />}
        {pending ? "Sending…" : "Request to Open Till"}
      </Button>
    </div>
  );
}
