"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { Check, Clock, Download, Loader2, Printer } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { formatAccountNo } from "@/lib/accounts";
import { formatMoney } from "@/lib/banking";
import { formatDateTime } from "@/lib/lab";
import { downloadReceipt, openReceipt, TYPE_LABEL } from "@/lib/transactions";
import type { TransactionOut } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { errorText } from "@/components/lab/common";
import { StatusBadge } from "@/components/shared/status-badge";
import { CopyRef, DetailRow, TypeBadge } from "./txn-result-parts";

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

const AMOUNT_LABEL: Record<string, string> = {
  cash_deposit: "Amount deposited",
  cash_withdrawal: "Amount withdrawn",
  transfer: "Amount transferred",
};

const acct = (no: number, name?: string | null) =>
  `${formatAccountNo(no)}${name ? ` – ${name}` : ""}`;

/** Modal shown after a transaction is submitted; any close starts a new one. */
export function TxnResult({
  sid,
  txn,
  onNew,
  tillCode,
}: {
  sid: string;
  txn: TransactionOut;
  onNew: () => void;
  tillCode?: string | null;
}) {
  const pending = txn.status === "pending_approval";
  const Icon = pending ? Clock : Check;
  const typeLabel = TYPE_LABEL[txn.type] ?? txn.type;
  const newRef = useRef<HTMLButtonElement>(null);
  const [busy, setBusy] = useState<"print" | "pdf" | null>(null);

  async function run(kind: "print" | "pdf") {
    if (busy) return;
    setBusy(kind);
    try {
      if (kind === "print") await openReceipt(sid, txn.id);
      else await downloadReceipt(sid, txn.id, txn.ref_no);
    } catch (e) {
      toast.error(errorText(e));
    } finally {
      setBusy(null);
    }
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "p") {
      e.preventDefault();
      if (!pending) void run("print");
    } else if (e.key === "Enter" && !(e.target as HTMLElement).closest("button, a")) {
      e.preventDefault();
      onNew();
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onNew()} disablePointerDismissal>
      <DialogContent
        initialFocus={newRef}
        showClose
        backdropClassName="bg-bank-navy/60 backdrop-blur-sm motion-reduce:transition-none"
        onKeyDown={onKeyDown}
        className={cn(
          "max-w-[30rem] gap-0 rounded-2xl border-t-4 shadow-xl duration-200 motion-reduce:transition-none",
          pending ? "border-t-fin-pending" : "border-t-fin-success",
          "max-sm:top-auto max-sm:bottom-0 max-sm:left-0 max-sm:max-h-[90dvh] max-sm:w-full max-sm:max-w-none max-sm:translate-x-0 max-sm:translate-y-0 max-sm:rounded-b-none",
          "max-h-[90vh] overflow-y-auto",
        )}
      >
        <div className="px-6 pt-6 text-center">
          <span
            className={cn(
              "mx-auto flex size-16 animate-in items-center justify-center rounded-full duration-300 zoom-in-50 motion-reduce:animate-none",
              pending
                ? "bg-fin-pending-bg text-fin-pending"
                : "bg-fin-success-bg text-fin-success",
            )}
          >
            <Icon className="size-8" strokeWidth={2.5} aria-hidden />
          </span>
          <DialogTitle className="mt-3 text-lg">
            {pending ? "Awaiting manager approval" : "Transaction Successful"}
          </DialogTitle>
          <DialogDescription className="mt-1 text-sm text-text-muted">
            {pending
              ? "A manager must approve this transaction before it is posted"
              : `${typeLabel} has been posted successfully`}
          </DialogDescription>
          <p className="mt-4 text-xs text-text-muted">
            {AMOUNT_LABEL[txn.type] ?? "Amount"}
          </p>
          <p className="text-3xl font-bold tracking-tight text-text-strong tabular-nums">
            {formatMoney(txn.amount, txn.currency)}
          </p>
        </div>

        <dl className="mx-6 mt-4 divide-y divide-border border-t border-border">
          <DetailRow label="Type">
            <TypeBadge type={txn.type} label={typeLabel} />
          </DetailRow>
          <DetailRow label="Reference">
            <CopyRef value={txn.ref_no} />
          </DetailRow>
          {txn.type === "transfer" ? (
            <>
              <DetailRow label="From">{acct(txn.account_no, txn.customer_name)}</DetailRow>
              {txn.counter_account_no != null && (
                <DetailRow label="To">
                  {acct(txn.counter_account_no, txn.counter_customer_name)}
                </DetailRow>
              )}
            </>
          ) : (
            <DetailRow label="Account">{acct(txn.account_no, txn.customer_name)}</DetailRow>
          )}
          <DetailRow label="Date & time">{formatDateTime(txn.created_at)}</DetailRow>
          <DetailRow label="Teller">{txn.created_by_name}</DetailRow>
          {tillCode && <DetailRow label="Till">{tillCode}</DetailRow>}
          <DetailRow label="Status">
            <StatusBadge status={txn.status} label={pending ? "Pending" : "Posted"} />
          </DetailRow>
        </dl>

        <div className="space-y-2 px-6 pt-4 pb-5">
          <Button ref={newRef} className="h-11 w-full" onClick={onNew}>
            New transaction
          </Button>
          {!pending && (
            <div className="grid grid-cols-2 gap-2">
              <Button
                variant="outline"
                className="h-10"
                disabled={busy !== null}
                onClick={() => run("print")}
              >
                {busy === "print" ? <Loader2 className="animate-spin" /> : <Printer />}
                Print receipt
              </Button>
              <Button
                variant="outline"
                className="h-10"
                disabled={busy !== null}
                onClick={() => run("pdf")}
              >
                {busy === "pdf" ? <Loader2 className="animate-spin" /> : <Download />}
                Download PDF
              </Button>
            </div>
          )}
          <p className="text-center">
            <Link
              href={`/s/${sid}/transactions`}
              className="rounded text-sm font-medium text-bank-primary outline-none hover:underline focus-visible:ring-2 focus-visible:ring-bank-accent"
            >
              View in Transactions
            </Link>
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
