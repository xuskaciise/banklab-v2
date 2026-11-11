"use client";

import { BookOpen, X } from "lucide-react";
import { Dialog as DialogPrimitive } from "@base-ui/react/dialog";
import { formatMoney } from "@/lib/banking";
import { useLearning } from "@/lib/dashboard";
import { useSessionMe } from "@/lib/lab";
import { TYPE_LABEL } from "@/lib/transactions";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorMsg } from "@/components/lab/common";
import { StatusBadge } from "@/components/shared/status-badge";

/** True when this session shows the Dr/Cr panel (on, and not an exam). */
export function useLearningEnabled(sid: string) {
  const me = useSessionMe(sid);
  return !!me.data?.learning_panel && me.data.kind !== "exam";
}

const num = "px-3 py-2 text-right whitespace-nowrap tabular-nums";

function Body({ sid, txnId }: { sid: string; txnId: string }) {
  const q = useLearning(sid, txnId);
  if (q.isPending)
    return (
      <div className="space-y-3 p-5" role="status" aria-label="Loading">
        <Skeleton className="h-5 w-1/2" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-16 w-full" />
      </div>
    );
  if (q.isError)
    return (
      <div className="p-5">
        <ErrorMsg error={q.error} />
      </div>
    );
  const d = q.data;
  const cur = d.currency;
  return (
    <div className="space-y-4 overflow-y-auto p-5">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-medium text-text-strong">{TYPE_LABEL[d.type] ?? d.type}</span>
        <span className="font-mono text-xs text-text-muted">{d.ref_no}</span>
        <StatusBadge
          status={d.status}
          label={d.status === "pending_approval" ? "Pending" : undefined}
        />
        {d.journal_entry_no != null && (
          <span className="text-xs text-text-muted">Journal entry #{d.journal_entry_no}</span>
        )}
      </div>
      {d.note && (
        <p className="rounded-lg bg-fin-pending-bg px-3 py-2 text-sm text-fin-pending">
          {d.note}
        </p>
      )}
      {d.lines.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-border bg-bank-sky-light">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-xs uppercase">
                <th scope="col" className="px-3 py-2 text-left font-medium text-text-muted">
                  Account
                </th>
                <th scope="col" className="px-3 py-2 text-right font-semibold text-bank-primary">
                  Dr
                </th>
                <th scope="col" className="px-3 py-2 text-right font-semibold text-bank-accent">
                  Cr
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {d.lines.map((l, i) => {
                const dr = Number(l.debit) !== 0;
                const cr = Number(l.credit) !== 0;
                return (
                  <tr key={i}>
                    <td className="px-3 py-2">
                      <span className="font-mono text-xs text-text-muted">{l.gl_code}</span>
                      <span className="block text-text-strong">{l.gl_name}</span>
                    </td>
                    <td className={`${num} font-medium text-bank-primary`}>
                      {dr ? formatMoney(l.debit, l.currency) : "—"}
                    </td>
                    <td className={`${num} font-medium text-bank-accent`}>
                      {cr ? formatMoney(l.credit, l.currency) : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-border font-semibold">
                <th scope="row" className="px-3 py-2 text-left text-text-strong">
                  Total
                </th>
                <td className={`${num} text-bank-primary`}>{formatMoney(d.total_debit, cur)}</td>
                <td className={`${num} text-bank-accent`}>{formatMoney(d.total_credit, cur)}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
      <section>
        <h3 className="text-sm font-semibold text-text-strong">What happened</h3>
        <p className="mt-1 text-sm whitespace-pre-line text-text-body">{d.explanation}</p>
      </section>
    </div>
  );
}

/** Right-side slide-over showing the Dr/Cr journal lines of one transaction. */
export function LearningPanel({
  sid,
  txnId,
  onClose,
}: {
  sid: string;
  txnId: string | null;
  onClose: () => void;
}) {
  return (
    <DialogPrimitive.Root open={!!txnId} onOpenChange={(o) => !o && onClose()}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Backdrop className="fixed inset-0 z-[60] bg-bank-navy/40 transition-opacity data-[ending-style]:opacity-0 data-[starting-style]:opacity-0" />
        <DialogPrimitive.Popup className="fixed inset-y-0 right-0 z-[60] flex w-[28rem] max-w-[100vw] flex-col bg-card shadow-xl outline-none transition-transform duration-200 data-[ending-style]:translate-x-full data-[starting-style]:translate-x-full motion-reduce:transition-none">
          <div className="flex items-center gap-2 border-b border-border px-5 py-4">
            <BookOpen className="size-4 text-bank-primary" aria-hidden />
            <DialogPrimitive.Title className="flex-1 text-base font-semibold text-text-strong">
              Dr / Cr learning panel
            </DialogPrimitive.Title>
            <DialogPrimitive.Close
              aria-label="Close"
              className="inline-flex size-7 items-center justify-center rounded-md text-text-muted hover:bg-hover hover:text-text-strong focus-visible:ring-2 focus-visible:ring-bank-accent"
            >
              <X className="size-4" />
            </DialogPrimitive.Close>
          </div>
          <DialogPrimitive.Description className="sr-only">
            Debit and credit lines posted for this transaction
          </DialogPrimitive.Description>
          {txnId && <Body sid={sid} txnId={txnId} />}
          <div className="mt-auto border-t border-border bg-surface px-5 py-3 text-right">
            <Button variant="outline" onClick={onClose}>
              Close
            </Button>
          </div>
        </DialogPrimitive.Popup>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
