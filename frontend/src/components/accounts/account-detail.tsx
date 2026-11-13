"use client";

import { useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import {
  formatAccountNo,
  mandateLabel,
  useAccount,
  useCloseAccount,
} from "@/lib/accounts";
import { ApiError } from "@/lib/api/client";
import { formatCif } from "@/lib/customers";
import { formatDateTime } from "@/lib/lab";
import { FileText } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { ErrorMsg, QueryState } from "@/components/lab/common";
import { AccountCheques } from "./account-cheques";
import { CustomerProfile } from "@/components/transactions/customer-profile";

function closeErrorFor(e: unknown): Error {
  const code =
    e instanceof ApiError
      ? (e.body as { code?: string } | undefined)?.code
      : undefined;
  if (code === "balance_not_zero")
    return new Error(
      "The balance is not zero. Withdraw or transfer the remaining funds before closing.",
    );
  if (code === "account_not_active")
    return new Error("This account is already closed.");
  return e instanceof Error ? e : new Error("Something went wrong");
}

export function AccountDetailView({
  sessionId,
  id,
  canClose,
  canIssueChequebook = false,
  canStopCheque = false,
  canStatement = false,
}: {
  sessionId: string;
  id: string;
  canClose: boolean;
  canIssueChequebook?: boolean;
  canStopCheque?: boolean;
  canStatement?: boolean;
}) {
  const q = useAccount(sessionId, id);
  const close = useCloseAccount(sessionId, id);
  const [confirm, setConfirm] = useState(false);
  const [closeError, setCloseError] = useState<unknown>(null);

  return (
    <QueryState query={q}>
      {q.data && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-text-muted">
              <span>
                Mandate:{" "}
                <span className="text-text-strong">
                  {mandateLabel(q.data.mandate)}
                </span>
              </span>
              <span>
                Opened:{" "}
                <span className="text-text-strong">
                  {formatDateTime(q.data.opened_at)}
                </span>
              </span>
              {q.data.closed_at && (
                <span>
                  Closed:{" "}
                  <span className="text-text-strong">
                    {formatDateTime(q.data.closed_at)}
                  </span>
                </span>
              )}
              <Link
                href={`/s/${sessionId}/customers/${q.data.customer_id}`}
                className="font-medium text-bank-primary hover:underline"
              >
                Open customer file (CIF {formatCif(q.data.cif_no)})
              </Link>
            </div>
            {canStatement && (
              <Link
                href={`/s/${sessionId}/accounts/${id}/statement`}
                className={buttonVariants({ variant: "outline" })}
              >
                <FileText /> Statement
              </Link>
            )}
            {canClose && q.data.status === "active" && (
              <Button
                variant="destructive"
                onClick={() => {
                  setCloseError(null);
                  setConfirm(true);
                }}
              >
                Close account
              </Button>
            )}
          </div>
          <CustomerProfile sid={sessionId} account={q.data} />

          {q.data.product_allows_cheques && (
            <AccountCheques
              sid={sessionId}
              account={q.data}
              canIssue={canIssueChequebook}
              canStop={canStopCheque}
            />
          )}

          <ErrorMsg error={closeError} />

          <ConfirmDialog
            open={confirm}
            onOpenChange={setConfirm}
            title="Close this account?"
            description={
              <>
                Account {formatAccountNo(q.data.account_no)} will be closed and
                can no longer be used. The balance must be zero.
              </>
            }
            confirmLabel="Close account"
            destructive
            pending={close.isPending}
            onConfirm={() =>
              close.mutate(undefined, {
                onSuccess: () => {
                  setConfirm(false);
                  toast.success("Account closed");
                },
                onError: (e) => {
                  setConfirm(false);
                  setCloseError(closeErrorFor(e));
                },
              })
            }
          />
        </div>
      )}
    </QueryState>
  );
}
