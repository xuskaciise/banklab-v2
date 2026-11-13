"use client";

import {
  ArrowDownToLine,
  ArrowLeftRight,
  ArrowUpFromLine,
  BookOpenCheck,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ErrorMsg } from "@/components/lab/common";
import type { Kind } from "./type-selector";

const SUBMIT: Record<Kind, { label: string; icon: typeof ArrowDownToLine }> = {
  deposit: { label: "Submit Deposit", icon: ArrowDownToLine },
  withdrawal: { label: "Submit Withdrawal", icon: ArrowUpFromLine },
  cheque_withdrawal: { label: "Submit Cheque Withdrawal", icon: BookOpenCheck },
  transfer: { label: "Submit Transfer", icon: ArrowLeftRight },
};

/** Cancel + submit pinned at the bottom of the summary column. */
export function TxnActions({
  kind,
  valid,
  pending,
  error,
  onReset,
}: {
  kind: Kind;
  valid: boolean;
  pending: boolean;
  error: unknown;
  onReset: () => void;
}) {
  const { label, icon: Icon } = SUBMIT[kind];
  const cash = kind !== "transfer";
  return (
    <>
      <ErrorMsg error={error} />
      {!valid && (
        <p className="text-xs text-text-muted">
          Find the account{kind === "transfer" ? "s" : ""}, enter {kind === "cheque_withdrawal" ? "the cheque number, " : ""}an amount
          {cash ? " and the party details" : ""} to continue.
        </p>
      )}
      <div className="flex gap-2">
        <Button
          type="button"
          variant="outline"
          onClick={onReset}
          disabled={pending}
          className="h-10 flex-1"
        >
          Cancel
        </Button>
        <Button type="submit" disabled={!valid || pending} className="h-10 flex-[2]">
          {pending ? (
            <Loader2 className="size-4 animate-spin" aria-hidden />
          ) : (
            <Icon className="size-4" aria-hidden />
          )}
          {pending ? "Posting…" : label}
        </Button>
      </div>
    </>
  );
}
