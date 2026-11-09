"use client";

import { useState } from "react";
import { Receipt } from "lucide-react";
import { toast } from "sonner";
import { formatAccountNo } from "@/lib/accounts";
import { formatMoney } from "@/lib/banking";
import { formatDateTime } from "@/lib/lab";
import {
  STATUS_LABEL,
  TXN_PAGE_SIZE,
  TYPE_LABEL,
  useReverseTxn,
  useTransactions,
} from "@/lib/transactions";
import type { TransactionOut } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { EmptyState } from "@/components/shared/empty-state";
import { Pagination } from "@/components/shared/pagination";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  ErrorMsg,
  Loading,
  Select,
  StatusBadge,
  Table,
  Td,
  Th,
} from "@/components/lab/common";
import { ReceiptButton } from "./txn-result";

function ReverseDialog({
  sid,
  txn,
  onClose,
}: {
  sid: string;
  txn: TransactionOut;
  onClose: () => void;
}) {
  const rev = useReverseTxn(sid);
  const [reason, setReason] = useState("");
  const [err, setErr] = useState<string | null>(null);
  return (
    <Dialog open onOpenChange={(o) => !o && !rev.isPending && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Reverse {txn.ref_no}</DialogTitle>
          <DialogDescription>
            A reversing entry will be posted for{" "}
            {formatMoney(txn.amount, txn.currency)}. This cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <Textarea
          aria-label="Reason"
          rows={3}
          placeholder="Reason for reversal"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
        {err && <p className="text-sm text-fin-danger">{err}</p>}
        <ErrorMsg error={rev.error} />
        <DialogFooter>
          <Button variant="outline" disabled={rev.isPending} onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            disabled={rev.isPending}
            onClick={() => {
              if (!reason.trim()) return setErr("Enter a reason");
              setErr(null);
              rev.mutate(
                { id: txn.id, reason: reason.trim() },
                {
                  onSuccess: () => {
                    toast.success("Transaction reversed");
                    onClose();
                  },
                },
              );
            }}
          >
            {rev.isPending ? "Reversing…" : "Reverse"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function TxnsList({
  sid,
  canReverse,
}: {
  sid: string;
  canReverse: boolean;
}) {
  const [status, setStatus] = useState("");
  const [type, setType] = useState("");
  const [page, setPage] = useState(1);
  const [reversing, setReversing] = useState<TransactionOut | null>(null);
  const list = useTransactions(sid, { status, type, page });
  const filtered = !!(status || type);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Select
          aria-label="Type"
          value={type}
          onChange={(e) => {
            setPage(1);
            setType(e.target.value);
          }}
        >
          <option value="">All types</option>
          {["cash_deposit", "cash_withdrawal", "cheque_withdrawal", "transfer", "reversal"].map((t) => (
            <option key={t} value={t}>
              {TYPE_LABEL[t]}
            </option>
          ))}
        </Select>
        <Select
          aria-label="Status"
          value={status}
          onChange={(e) => {
            setPage(1);
            setStatus(e.target.value);
          }}
        >
          <option value="">All statuses</option>
          {Object.entries(STATUS_LABEL).map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </Select>
      </div>
      {list.isPending ? (
        <Loading label="Loading transactions" />
      ) : list.isError ? (
        <ErrorMsg error={list.error} />
      ) : list.data.items.length === 0 ? (
        <EmptyState
          icon={Receipt}
          title={filtered ? "No matching transactions" : "No transactions yet"}
          description={
            filtered ? "Try different filters." : "Posted transactions will appear here."
          }
        />
      ) : (
        <>
          <Table>
            <thead>
              <tr>
                <Th>Ref no</Th>
                <Th>Type</Th>
                <Th>Account</Th>
                <Th className="text-right">Amount</Th>
                <Th>Status</Th>
                <Th>Date</Th>
                <Th />
              </tr>
            </thead>
            <tbody>
              {list.data.items.map((t) => (
                <tr key={t.id} className="hover:bg-hover">
                  <Td className="font-mono text-xs">{t.ref_no}</Td>
                  <Td>
                    {TYPE_LABEL[t.type] ?? t.type}
                    {t.cheque_no != null && (
                      <span className="ml-1 font-mono text-xs text-text-muted">
                        #{t.cheque_no}
                      </span>
                    )}
                  </Td>
                  <Td>
                    <span className="font-mono text-xs">
                      {formatAccountNo(t.account_no)}
                    </span>
                    {t.counter_account_no != null && (
                      <span className="font-mono text-xs text-text-muted">
                        {" → "}
                        {formatAccountNo(t.counter_account_no)}
                      </span>
                    )}
                    <div className="text-xs text-text-muted">{t.customer_name}</div>
                  </Td>
                  <Td className="text-right font-medium whitespace-nowrap text-text-strong tabular-nums">
                    {formatMoney(t.amount, t.currency)}
                  </Td>
                  <Td>
                    <StatusBadge status={t.status} label={STATUS_LABEL[t.status]} />
                  </Td>
                  <Td className="whitespace-nowrap text-text-muted">
                    {formatDateTime(t.created_at)}
                  </Td>
                  <Td>
                    <div className="flex justify-end gap-2">
                      {(t.status === "posted" || t.status === "reversed") && (
                        <ReceiptButton sid={sid} id={t.id} />
                      )}
                      {canReverse && t.status === "posted" && t.type !== "reversal" && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setReversing(t)}
                        >
                          Reverse
                        </Button>
                      )}
                    </div>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
          <Pagination
            page={page}
            pageSize={TXN_PAGE_SIZE}
            total={list.data.count}
            onPageChange={setPage}
          />
        </>
      )}
      {reversing && (
        <ReverseDialog sid={sid} txn={reversing} onClose={() => setReversing(null)} />
      )}
    </div>
  );
}
