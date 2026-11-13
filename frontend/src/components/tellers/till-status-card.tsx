"use client";

import {
  ArrowDownToLine,
  ArrowUpFromLine,
  Check,
  Landmark,
} from "lucide-react";
import { formatDateTime } from "@/lib/lab";
import { formatMoney } from "@/lib/banking";
import type { TellerSession } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { SessionStatus } from "./session-bits";

const STEPS = [
  { key: "requested", label: "Requested" },
  { key: "open", label: "Open" },
  { key: "closing", label: "Count submitted" },
  { key: "closed", label: "Closed" },
] as const;

const STEP_INDEX: Record<string, number> = {
  pending_open: 0,
  open: 1,
  closing: 2,
  closed: 3,
  cancelled: 0,
};

const HINT: Record<string, string> = {
  pending_open: "Waiting for your manager to approve opening this till.",
  open: "Your till is open. You can serve customers.",
  closing:
    "Your count was submitted. Waiting for your manager to approve closing.",
  closed:
    "This till is closed for the day. All cash was returned to the vault.",
  cancelled: "This opening request was cancelled.",
};

/** Till header: code, status, a one-line hint and the day's lifecycle. */
export function TillStatusCard({
  s,
  children,
}: {
  s: TellerSession;
  children?: React.ReactNode;
}) {
  const at = STEP_INDEX[s.status] ?? 0;
  const times: Record<string, string | null | undefined> = {
    requested: s.open_requested_at,
    open: s.opened_at,
    closing: s.close_requested_at,
    closed: s.closed_at,
  };
  return (
    <section className="rounded-xl border border-border bg-card shadow-xs">
      <div className="flex flex-wrap items-start justify-between gap-4 p-5">
        <div className="flex items-start gap-3">
          <span
            aria-hidden
            className="flex size-11 shrink-0 items-center justify-center rounded-lg bg-bank-sky-light text-bank-primary"
          >
            <Landmark className="size-5" />
          </span>
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-lg font-semibold text-text-strong">
                Till <span className="font-mono">{s.till_code}</span>
              </h2>
              <SessionStatus status={s.status} />
            </div>
            <p className="text-sm text-text-muted">{HINT[s.status] ?? ""}</p>
          </div>
        </div>
        {children && <div className="flex flex-wrap gap-2">{children}</div>}
      </div>
      <ol className="grid grid-cols-2 gap-3 border-t border-border px-5 py-4 sm:grid-cols-4">
        {STEPS.map((step, i) => {
          const done = i < at || (i === at && s.status === "closed");
          const current = i === at && s.status !== "closed";
          return (
            <li key={step.key} className="flex items-start gap-2.5">
              <span
                aria-hidden
                className={cn(
                  "mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full border text-xs font-semibold",
                  done && "border-bank-primary bg-bank-primary text-white",
                  current &&
                    "border-bank-primary bg-bank-sky-light text-bank-primary",
                  !done && !current && "border-border bg-card text-text-muted",
                )}
              >
                {done ? <Check className="size-3.5" strokeWidth={3} /> : i + 1}
              </span>
              <div className="min-w-0">
                <p
                  className={cn(
                    "text-sm font-medium",
                    done || current ? "text-text-strong" : "text-text-muted",
                  )}
                >
                  {step.label}
                  {current && <span className="sr-only"> (current step)</span>}
                </p>
                <p className="truncate text-xs text-text-muted">
                  {times[step.key] ? formatDateTime(times[step.key]) : "—"}
                </p>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

/** Cash moving between the vault and this till that still needs approval. */
export function PendingTransfers({ s }: { s: TellerSession }) {
  if (!s.pending_transfers.length) return null;
  return (
    <section className="rounded-xl border border-border bg-card shadow-xs">
      <header className="border-b border-border px-5 py-3">
        <h3 className="text-sm font-semibold text-text-strong">
          Pending cash transfers
        </h3>
        <p className="text-xs text-text-muted">
          Cash moves only after the vault custodian and your manager approve it.
        </p>
      </header>
      <ul className="divide-y divide-border">
        {s.pending_transfers.map((t) => {
          const inbound = t.direction === "vault_to_teller";
          const Icon = inbound ? ArrowDownToLine : ArrowUpFromLine;
          return (
            <li key={t.id} className="flex items-center gap-3 px-5 py-3">
              <span
                aria-hidden
                className={cn(
                  "flex size-9 shrink-0 items-center justify-center rounded-lg",
                  inbound
                    ? "bg-fin-success-bg text-fin-success-dark"
                    : "bg-hover text-text-body",
                )}
              >
                <Icon className="size-4" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-text-strong">
                  {inbound ? "Opening float from vault" : "Cash back to vault"}
                </p>
                <p className="text-xs text-text-muted capitalize">
                  {t.status.replace(/_/g, " ")}
                </p>
              </div>
              <span className="text-base font-semibold text-text-strong tabular-nums">
                {formatMoney(t.amount, t.currency)}
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
