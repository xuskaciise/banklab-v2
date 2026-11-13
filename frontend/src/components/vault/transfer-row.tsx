"use client";

import { ArrowDown, ArrowUp, Check, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatMoney } from "@/lib/banking";
import type { CashTransferOut } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/shared/status-badge";
import { directionOf, fmtWhen, STATUS_LABEL, stepsOf, titleCase } from "./vault-utils";

export const ROW_GRID =
  "md:grid md:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)_minmax(0,1.2fr)_minmax(0,1.5fr)_minmax(0,.9fr)_9.5rem] md:items-center md:gap-3";

export function DirectionBadge({ t }: { t: CashTransferOut }) {
  const d = directionOf(t);
  if (d === "to_till")
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-fin-pending-bg px-2 py-0.5 text-xs font-medium text-fin-pending">
        <ArrowUp className="size-3" aria-hidden />
        To till
      </span>
    );
  if (d === "to_vault")
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-fin-success-bg px-2 py-0.5 text-xs font-medium text-fin-success-dark">
        <ArrowDown className="size-3" aria-hidden />
        To vault
      </span>
    );
  return (
    <span className="inline-flex rounded-full bg-hover px-2 py-0.5 text-xs font-medium text-text-body">
      Till to till
    </span>
  );
}

/** Mini stepper Requested -> Custodian -> Manager -> Posted; approver in the tooltip. */
export function Progress({ t }: { t: CashTransferOut }) {
  const rejected = t.status === "rejected";
  const steps = stepsOf(t);
  const current = steps.findIndex((s) => !s.done);
  return (
    <ol className="flex items-center gap-1" aria-label="Approval progress">
      {steps.map((s, i) => {
        const cur = !rejected && i === current;
        return (
          <li
            key={s.label}
            title={`${s.label}${s.by ? ` · ${s.by}` : ""}`}
            className="flex items-center gap-1"
          >
            <span
              className={cn(
                "flex size-5 items-center justify-center rounded-full border text-[10px] font-semibold",
                s.done && "border-fin-success bg-fin-success text-white",
                cur && "border-fin-pending bg-fin-pending-bg text-fin-pending",
                !s.done && !cur && "border-border bg-card text-text-muted",
                rejected && i === current && "border-fin-danger bg-fin-danger text-white",
              )}
            >
              {s.done ? (
                <Check className="size-3" strokeWidth={3} aria-hidden />
              ) : rejected && i === current ? (
                <X className="size-3" strokeWidth={3} aria-hidden />
              ) : (
                i + 1
              )}
              <span className="sr-only">{s.label}</span>
            </span>
            {i < steps.length - 1 && (
              <span aria-hidden className={cn("h-px w-3", s.done ? "bg-fin-success" : "bg-border")} />
            )}
          </li>
        );
      })}
    </ol>
  );
}

export function TransferRow({
  t,
  mine,
  onApprove,
  onReject,
  onView,
  busy,
}: {
  t: CashTransferOut;
  mine: "approve-custodian" | "approve-manager" | null;
  onApprove: () => void;
  onReject: () => void;
  onView: () => void;
  busy: boolean;
}) {
  const tone =
    t.status === "posted"
      ? "success"
      : t.status === "rejected"
        ? "danger"
        : "pending";
  return (
    <li
      className={cn(
        "space-y-2 px-4 py-3 text-sm max-md:rounded-lg max-md:border max-md:border-border",
        ROW_GRID,
        mine && "bg-fin-pending-bg/40",
      )}
    >
      <p className="min-w-0 font-medium break-words text-text-strong">
        {titleCase(t.from_label)} <span className="text-text-muted">→</span> {titleCase(t.to_label)}
      </p>
      <p className="font-semibold text-text-strong tabular-nums md:text-right" title={formatMoney(t.amount, t.currency)}>
        {formatMoney(t.amount, t.currency)}
      </p>
      <div className="min-w-0">
        <p className="truncate text-text-body">{t.requested_by_name}</p>
        <p className="text-xs text-text-muted">{fmtWhen(t.created_at)}</p>
      </div>
      <Progress t={t} />
      <div>
        <StatusBadge status={t.status} label={STATUS_LABEL[t.status] ?? t.status} tone={tone} />
      </div>
      <div className="flex gap-2 md:justify-end">
        {mine ? (
          <>
            <Button size="sm" disabled={busy} onClick={onApprove}>
              Approve
            </Button>
            <Button size="sm" variant="outline" disabled={busy} onClick={onReject}>
              Reject
            </Button>
          </>
        ) : (
          <Button size="sm" variant="outline" onClick={onView}>
            View
          </Button>
        )}
      </div>
    </li>
  );
}
