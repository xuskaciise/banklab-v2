"use client";

import { useState } from "react";
import { toast } from "sonner";
import { LEAF_OPTIONS, useIssueChequebook, useStopCheque } from "@/lib/cheques";
import { cn } from "@/lib/utils";
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
import { ErrorMsg } from "@/components/lab/common";

export function IssueChequebookDialog({
  sid,
  aid,
  onClose,
}: {
  sid: string;
  aid: string;
  onClose: () => void;
}) {
  const issue = useIssueChequebook(sid, aid);
  const [leaves, setLeaves] = useState<number>(25);
  return (
    <Dialog open onOpenChange={(o) => !o && !issue.isPending && onClose()}>
      <DialogContent>
        <form
          noValidate
          className="flex min-h-0 flex-col"
          onSubmit={(e) => {
            e.preventDefault();
            issue.mutate(leaves, {
              onSuccess: (b) => {
                toast.success(`Chequebook issued: ${b.first_no} to ${b.last_no}`);
                onClose();
              },
            });
          }}
        >
          <DialogHeader>
            <DialogTitle>Issue chequebook</DialogTitle>
          </DialogHeader>
          <DialogBody className="space-y-3">
            <div
              role="radiogroup"
              aria-label="Number of leaves"
              className="grid grid-cols-3 gap-2"
            >
              {LEAF_OPTIONS.map((n) => (
                <button
                  key={n}
                  type="button"
                  role="radio"
                  aria-checked={leaves === n}
                  onClick={() => setLeaves(n)}
                  className={cn(
                    "rounded-lg border px-3 py-3 text-center text-sm font-medium outline-none transition-colors",
                    "focus-visible:ring-2 focus-visible:ring-bank-accent",
                    leaves === n
                      ? "border-bank-primary bg-bank-sky-light text-bank-primary"
                      : "border-border text-text-body hover:bg-hover",
                  )}
                >
                  <span className="block text-lg font-semibold tabular-nums">{n}</span>
                  leaves
                </button>
              ))}
            </div>
            <p className="text-xs text-text-muted">
              Cheque numbers are assigned by the system in sequence.
            </p>
            <ErrorMsg error={issue.error} />
          </DialogBody>
          <DialogFooter>
            <Button type="button" variant="outline" disabled={issue.isPending} onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={issue.isPending}>
              {issue.isPending ? "Issuing…" : "Issue chequebook"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function StopChequeDialog({
  sid,
  aid,
  cheque,
  onClose,
}: {
  sid: string;
  aid: string;
  cheque: { id: string; number: number };
  onClose: () => void;
}) {
  const stop = useStopCheque(sid, aid);
  const [reason, setReason] = useState("");
  const [attempted, setAttempted] = useState(false);
  const err = attempted && !reason.trim() ? "A reason is required" : undefined;
  return (
    <Dialog open onOpenChange={(o) => !o && !stop.isPending && onClose()}>
      <DialogContent>
        <form
          noValidate
          className="flex min-h-0 flex-col"
          onSubmit={(e) => {
            e.preventDefault();
            if (!reason.trim()) return setAttempted(true);
            stop.mutate(
              { id: cheque.id, reason: reason.trim() },
              {
                onSuccess: () => {
                  toast.success(`Cheque ${cheque.number} stopped`);
                  onClose();
                },
              },
            );
          }}
        >
          <DialogHeader>
            <DialogTitle>Stop cheque {cheque.number}</DialogTitle>
          </DialogHeader>
          <DialogBody className="space-y-3">
            <p className="text-sm text-text-muted">
              A stopped cheque can no longer be paid. This cannot be undone.
            </p>
            <div className="space-y-1">
              <label htmlFor="stop-reason" className="text-sm font-medium text-text-strong">
                Reason <span className="text-fin-danger">*</span>
              </label>
              <Textarea
                id="stop-reason"
                rows={3}
                value={reason}
                aria-invalid={!!err}
                onChange={(e) => setReason(e.target.value)}
              />
              {err && <p className="text-sm text-fin-danger">{err}</p>}
            </div>
            <ErrorMsg error={stop.error} />
          </DialogBody>
          <DialogFooter>
            <Button type="button" variant="outline" disabled={stop.isPending} onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" variant="destructive" disabled={stop.isPending}>
              {stop.isPending ? "Stopping…" : "Stop cheque"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
