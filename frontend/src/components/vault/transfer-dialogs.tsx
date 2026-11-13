"use client";

import { formatMoney } from "@/lib/banking";
import type { CashTransferOut } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { DirectionBadge, Progress } from "./transfer-row";
import { fmtWhen, STATUS_LABEL, titleCase } from "./vault-utils";

const route = (t: CashTransferOut) => `${titleCase(t.from_label)} → ${titleCase(t.to_label)}`;

export function ApproveDialog({
  t,
  step,
  pending,
  onClose,
  onConfirm,
}: {
  t: CashTransferOut | null;
  step: string;
  pending: boolean;
  onClose: () => void;
  onConfirm: () => void;
}) {
  return (
    <ConfirmDialog
      open={!!t}
      onOpenChange={(o) => !o && onClose()}
      title={step === "approve-manager" ? "Approve and post transfer" : "Approve transfer"}
      description={
        t && (
          <span className="block space-y-1">
            <span className="block text-2xl font-semibold text-text-strong tabular-nums">
              {formatMoney(t.amount, t.currency)}
            </span>
            <span className="block">{route(t)}</span>
            <span className="block text-xs">Requested by {t.requested_by_name}</span>
          </span>
        )
      }
      confirmLabel={step === "approve-manager" ? "Approve and post" : "Approve"}
      pending={pending}
      onConfirm={onConfirm}
    />
  );
}

export function RejectDialog({
  t,
  reason,
  setReason,
  err,
  pending,
  onClose,
  onConfirm,
}: {
  t: CashTransferOut | null;
  reason: string;
  setReason: (v: string) => void;
  err: string | null;
  pending: boolean;
  onClose: () => void;
  onConfirm: () => void;
}) {
  return (
    <ConfirmDialog
      open={!!t}
      onOpenChange={(o) => !o && onClose()}
      title="Reject cash transfer"
      description={
        <span className="block space-y-3">
          <span className="block">
            {t && `${formatMoney(t.amount, t.currency)} requested by ${t.requested_by_name}.`}
          </span>
          <Textarea
            aria-label="Reason"
            placeholder="Reason for rejection"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          {err && <span className="block text-sm text-fin-danger">{err}</span>}
        </span>
      }
      confirmLabel="Reject transfer"
      destructive
      pending={pending}
      onConfirm={onConfirm}
    />
  );
}

export function DetailsDialog({
  t,
  canReject,
  onReject,
  onClose,
}: {
  t: CashTransferOut | null;
  canReject: boolean;
  onReject: () => void;
  onClose: () => void;
}) {
  const rows: [string, React.ReactNode][] = t
    ? [
        ["Direction", <DirectionBadge key="d" t={t} />],
        ["Transfer", route(t)],
        ["Amount", <span key="a" className="font-semibold tabular-nums">{formatMoney(t.amount, t.currency)}</span>],
        ["Status", STATUS_LABEL[t.status] ?? t.status],
        ["Requested by", `${t.requested_by_name} · ${fmtWhen(t.created_at)}`],
        ["Custodian", t.approved_by_1_name ?? "—"],
        ["Manager", t.approved_by_2_name ?? "—"],
        ...(t.reason ? [["Reason", t.reason] as [string, string]] : []),
        ["Last update", fmtWhen(t.updated_at)],
      ]
    : [];
  return (
    <Dialog open={!!t} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Transfer details</DialogTitle>
        </DialogHeader>
        <DialogBody className="space-y-3">
          {t && <Progress t={t} />}
          <dl className="divide-y divide-border text-sm">
            {rows.map(([k, v]) => (
              <div key={k} className="flex justify-between gap-4 py-2">
                <dt className="text-text-muted">{k}</dt>
                <dd className="text-right font-medium text-text-strong">{v}</dd>
              </div>
            ))}
          </dl>
        </DialogBody>
        <DialogFooter>
          {canReject && (
            <Button variant="outline" onClick={onReject}>
              Reject
            </Button>
          )}
          <Button onClick={onClose}>Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
