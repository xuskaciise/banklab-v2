"use client";

import { Info, Landmark, Loader2, Send } from "lucide-react";
import { formatMoney } from "@/lib/banking";
import { Tooltip } from "@/components/ui/tooltip";
import { AmountInput, amountValid, stripAmount } from "./amount-input";
import type { TillAvailability } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { FormSection } from "@/components/shared/form-layout";
import { StatusBadge } from "@/components/shared/status-badge";
import { ErrorMsg } from "@/components/lab/common";
import { CURRENCIES } from "./session-bits";

/** Float is optional; every filled value must be digits (USD max 2 decimals). */
export function floatsValid(floats: Record<string, string>) {
  return CURRENCIES.every((c) =>
    amountValid(floats[c] ?? "", c === "USD" ? 2 : 0),
  );
}

/** Compact one-line summary of the selected till, shown under the combobox. */
export function TillSummary({ till }: { till: TillAvailability | undefined }) {
  if (!till)
    return (
      <p className="flex items-center gap-2 text-sm text-text-muted">
        <Landmark className="size-4" aria-hidden />
        Choose a free till from the list.
      </p>
    );
  const item = "min-w-0 space-y-0.5";
  const label =
    "text-[11px] font-medium tracking-wide text-text-muted uppercase";
  return (
    <dl className="flex flex-wrap items-center gap-x-6 gap-y-3 rounded-lg border border-border bg-surface px-4 py-3 text-sm">
      <span
        aria-hidden
        className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-bank-sky-light text-bank-primary"
      >
        <Landmark className="size-4" />
      </span>
      <div className={item}>
        <dt className={label}>Till</dt>
        <dd className="flex items-center gap-2">
          <span className="font-mono font-semibold text-text-strong">
            {till.code}
          </span>
          <StatusBadge status="open" label="Free" />
        </dd>
      </div>
      <div className={item}>
        <dt className={label}>Branch</dt>
        <dd className="truncate text-text-strong">
          {till.branch_name}{" "}
          <span className="text-xs text-text-muted">{till.branch_code}</span>
        </dd>
      </div>
      <div className={item}>
        <dt className={label}>Location</dt>
        <dd
          className={
            till.branch_address ? "truncate text-text-body" : "text-text-muted"
          }
        >
          {till.branch_address || "No address"}
        </dd>
      </div>
    </dl>
  );
}

/** Opening float, request summary, notice and submit. */
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
  const ready = !!till && till.available && valid;
  const money = (c: string) => {
    const raw = stripAmount(floats[c] ?? "").trim();
    return raw && amountValid(raw, c === "USD" ? 2 : 0) && raw !== "."
      ? formatMoney(raw, c)
      : "—";
  };
  return (
    <>
      <FormSection title="Opening Cash Float">
        <div className="grid gap-4 sm:grid-cols-2">
          {CURRENCIES.map((c) => (
            <AmountInput
              key={c}
              currency={c}
              decimals={c === "USD" ? 2 : 0}
              value={floats[c] ?? ""}
              onChange={(v) => onFloats({ ...floats, [c]: v })}
            />
          ))}
        </div>
        <p className="flex gap-2.5 rounded-lg border border-bank-accent/30 bg-bank-sky-light p-3 text-sm leading-relaxed text-bank-primary">
          <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
          An opening cash float is requested from the vault and requires manager
          approval before the till becomes operational.
        </p>
      </FormSection>

      <div className="space-y-4 lg:sticky lg:top-4 lg:col-start-2 lg:row-span-2 lg:row-start-1">
        <FormSection title="Request summary">
          <dl className="divide-y divide-border text-sm">
            {[
              ["Till", till ? `${till.code} · ${till.branch_name}` : "—"],
              ["USD float", money("USD")],
              ["SOS float", money("SOS")],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between gap-3 py-2">
                <dt className="text-text-muted">{k}</dt>
                <dd className="font-medium text-text-strong tabular-nums">
                  {v}
                </dd>
              </div>
            ))}
          </dl>
        </FormSection>

        {err && <ErrorMsg error={new Error(err)} />}
        <div className="space-y-2">
          <Tooltip
            content="Select a till to continue"
            side="top"
            disabled={ready || pending}
          >
            <span className="block">
              <Button
                type="submit"
                size="lg"
                disabled={pending || !ready}
                className="w-full disabled:cursor-not-allowed disabled:bg-hover disabled:text-text-muted disabled:opacity-100"
              >
                {pending ? <Loader2 className="animate-spin" /> : <Send />}
                {pending ? "Sending request…" : "Request to Open Till"}
              </Button>
            </span>
          </Tooltip>
          {!ready && !pending && (
            <p className="text-center text-xs text-text-muted">
              {!till
                ? "Select a till to continue."
                : "Fix the float amounts to continue."}
            </p>
          )}
        </div>
      </div>
    </>
  );
}
