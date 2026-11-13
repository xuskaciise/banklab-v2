"use client";

import { useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { dateLabel } from "@/lib/eod";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/shared/checkbox";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export function ConfirmCloseDialog({
  open,
  onOpenChange,
  date,
  next,
  pending,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  date: string;
  next: string;
  pending: boolean;
  onConfirm: () => void;
}) {
  const [ok, setOk] = useState(false);
  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (pending) return;
        setOk(false);
        onOpenChange(o);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Close business day</DialogTitle>
          <DialogDescription>
            {dateLabel(date)} will be locked and {dateLabel(next)} will become the business date. This cannot be
            undone.
          </DialogDescription>
        </DialogHeader>
        <DialogBody>
          <label className="flex cursor-pointer items-start gap-2 text-sm text-text-body">
            <Checkbox className="mt-0.5" checked={ok} onChange={(e) => setOk(e.target.checked)} />
            I have reviewed the checks and the day&apos;s summary.
          </label>
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" disabled={pending} onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button disabled={!ok || pending} onClick={onConfirm}>
            {pending ? "Closing…" : "Confirm & close day"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function ClosedDialog({
  result,
  onBack,
  onDismiss,
}: {
  result: { closed: string; next: string } | null;
  onBack: () => void;
  onDismiss: () => void;
}) {
  return (
    <Dialog open={!!result} onOpenChange={(o) => !o && onDismiss()}>
      <DialogContent>
        <DialogBody className="flex flex-col items-center gap-2 py-8 text-center">
          <CheckCircle2 className="size-12 text-fin-success" aria-hidden />
          <DialogTitle>Business day {result ? dateLabel(result.closed) : ""} closed</DialogTitle>
          <DialogDescription>{result ? dateLabel(result.next) : ""} is now open.</DialogDescription>
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={onDismiss}>
            Stay here
          </Button>
          <Button onClick={onBack}>Back to dashboard</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
