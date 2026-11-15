"use client";

import { AmountWords } from "@/components/shared/amount-words";
import { useState } from "react";
import { ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { formatAccountNo } from "@/lib/accounts";
import { formatMoney } from "@/lib/banking";
import { formatDateTime } from "@/lib/lab";
import { TYPE_LABEL, useApprovals, useDecideApproval } from "@/lib/transactions";
import type { ApprovalOut } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { EmptyState } from "@/components/shared/empty-state";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ErrorMsg, Loading, Table, Td, Th } from "@/components/lab/common";

type Pick = { approval: ApprovalOut; decision: "approve" | "reject" };

function DecideDialog({
  sid,
  pick,
  onClose,
}: {
  sid: string;
  pick: Pick;
  onClose: () => void;
}) {
  const decide = useDecideApproval(sid);
  const [note, setNote] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const approve = pick.decision === "approve";
  const t = pick.approval.transaction;
  return (
    <Dialog open onOpenChange={(o) => !o && !decide.isPending && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{approve ? "Approve" : "Reject"} transaction</DialogTitle>
          <DialogDescription>
            {t ? `${t.ref_no} · ${formatMoney(t.amount, t.currency)}` : "Pending request"}
            {approve ? " will be posted to the ledger." : " will not be posted."}
          </DialogDescription>
          {t && <AmountWords text={t.amount_in_words} />}
        </DialogHeader>
        <Textarea
          aria-label="Note"
          rows={3}
          placeholder={approve ? "Note (optional)" : "Reason for rejection"}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
        {err && <p className="text-sm text-fin-danger">{err}</p>}
        <ErrorMsg error={decide.error} />
        <DialogFooter>
          <Button variant="outline" disabled={decide.isPending} onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant={approve ? "default" : "destructive"}
            disabled={decide.isPending}
            onClick={() => {
              if (!approve && !note.trim()) return setErr("Enter a reason");
              setErr(null);
              decide.mutate(
                { id: pick.approval.id, decision: pick.decision, note: note.trim() },
                {
                  onSuccess: () => {
                    toast.success(approve ? "Approved and posted" : "Rejected");
                    onClose();
                  },
                },
              );
            }}
          >
            {decide.isPending ? "Working…" : approve ? "Approve" : "Reject"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function ApprovalsList({ sid, readOnly }: { sid: string; readOnly: boolean }) {
  const list = useApprovals(sid);
  const [pick, setPick] = useState<Pick | null>(null);

  if (list.isPending) return <Loading label="Loading approvals" />;
  if (list.isError) return <ErrorMsg error={list.error} />;
  if (list.data.length === 0)
    return (
      <EmptyState
        icon={ShieldCheck}
        title="Nothing waiting"
        description="Transactions above a teller's limit will appear here for approval."
      />
    );
  return (
    <>
      <Table>
        <thead>
          <tr>
            <Th>Requested by</Th>
            <Th>Type</Th>
            <Th>Account</Th>
            <Th className="text-right">Amount</Th>
            <Th>Party</Th>
            <Th>Requested</Th>
            <Th />
          </tr>
        </thead>
        <tbody>
          {list.data.map((a) => {
            const t = a.transaction;
            return (
              <tr key={a.id} className="hover:bg-hover">
                <Td className="font-medium text-text-strong">{a.requested_by_name}</Td>
                <Td>
                  {t ? (TYPE_LABEL[t.type] ?? t.type) : a.reason}
                  {t?.cheque_no != null && (
                    <span className="ml-1 font-mono text-xs text-text-muted">
                      #{t.cheque_no}
                    </span>
                  )}
                </Td>
                <Td>
                  {t && (
                    <>
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
                    </>
                  )}
                </Td>
                <Td className="text-right font-medium whitespace-nowrap text-text-strong tabular-nums">
                  {t ? formatMoney(t.amount, t.currency) : ""}
                </Td>
                <Td>{t?.party_name || "—"}</Td>
                <Td className="whitespace-nowrap text-text-muted">
                  {formatDateTime(a.created_at)}
                </Td>
                <Td>
                  {!readOnly && (
                    <div className="flex justify-end gap-2">
                      <Button size="sm" onClick={() => setPick({ approval: a, decision: "approve" })}>
                        Approve
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setPick({ approval: a, decision: "reject" })}
                      >
                        Reject
                      </Button>
                    </div>
                  )}
                </Td>
              </tr>
            );
          })}
        </tbody>
      </Table>
      {pick && <DecideDialog sid={sid} pick={pick} onClose={() => setPick(null)} />}
    </>
  );
}
