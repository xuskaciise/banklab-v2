"use client";

import { useState } from "react";
import { CheckCircle2, Clock } from "lucide-react";
import { toast } from "sonner";
import { formatMoney } from "@/lib/banking";
import { openReceipt, TYPE_LABEL } from "@/lib/transactions";
import type { TransactionOut } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { errorText } from "@/components/lab/common";

export function ReceiptButton({ sid, id }: { sid: string; id: string }) {
  const [busy, setBusy] = useState(false);
  return (
    <Button
      variant="outline"
      size="sm"
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        try {
          await openReceipt(sid, id);
        } catch (e) {
          toast.error(errorText(e));
        } finally {
          setBusy(false);
        }
      }}
    >
      {busy ? "Opening…" : "Receipt"}
    </Button>
  );
}

export function TxnResult({
  sid,
  txn,
  onNew,
}: {
  sid: string;
  txn: TransactionOut;
  onNew: () => void;
}) {
  const pending = txn.status === "pending_approval";
  const Icon = pending ? Clock : CheckCircle2;
  return (
    <div
      role="status"
      className={`max-w-xl space-y-3 rounded-xl border p-5 ${
        pending
          ? "border-fin-pending/30 bg-fin-pending-bg"
          : "border-fin-success/30 bg-fin-success-bg"
      }`}
    >
      <div className="flex items-center gap-2">
        <Icon
          className={`size-5 ${pending ? "text-fin-pending" : "text-fin-success-dark"}`}
        />
        <p className="font-semibold text-text-strong">
          {pending ? "Waiting for manager approval" : "Posted"}
        </p>
      </div>
      <p className="text-sm text-text-body">
        {TYPE_LABEL[txn.type] ?? txn.type} of{" "}
        <span className="font-medium tabular-nums">
          {formatMoney(txn.amount, txn.currency)}
        </span>
        . Ref <span className="font-mono">{txn.ref_no}</span>
      </p>
      {pending && (
        <p className="text-sm text-text-muted">
          The amount is above your limit. It will post once a manager approves it.
        </p>
      )}
      <div className="flex gap-2">
        {!pending && <ReceiptButton sid={sid} id={txn.id} />}
        <Button size="sm" onClick={onNew}>
          New transaction
        </Button>
      </div>
    </div>
  );
}
