"use client";

import { useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import {
  formatAccountNo,
  mandateLabel,
  statusLabel,
  useAccount,
  useCloseAccount,
} from "@/lib/accounts";
import { ApiError } from "@/lib/api/client";
import { formatMoney } from "@/lib/banking";
import { formatCif } from "@/lib/customers";
import { formatDateTime } from "@/lib/lab";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { StatusBadge } from "@/components/shared/status-badge";
import { ErrorMsg, QueryState } from "@/components/lab/common";

function closeErrorFor(e: unknown): Error {
  const code =
    e instanceof ApiError ? (e.body as { code?: string } | undefined)?.code : undefined;
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
}: {
  sessionId: string;
  id: string;
  canClose: boolean;
}) {
  const q = useAccount(sessionId, id);
  const close = useCloseAccount(sessionId, id);
  const [confirm, setConfirm] = useState(false);
  const [closeError, setCloseError] = useState<unknown>(null);

  return (
    <QueryState query={q}>
      {q.data && (
        <div className="space-y-6">
          <section className="flex flex-wrap items-start justify-between gap-4 rounded-xl border border-border bg-card p-5 shadow-xs">
            <div className="min-w-0 space-y-3">
              <p className="font-mono text-xs text-text-muted">
                Account {formatAccountNo(q.data.account_no)}
              </p>
              <h2 className="flex flex-wrap items-center gap-3 text-xl font-semibold text-text-strong">
                {q.data.product_name}
                <StatusBadge
                  status={q.data.status}
                  label={statusLabel(q.data.status)}
                />
              </h2>
              <p className="text-2xl font-semibold text-text-strong tabular-nums">
                {formatMoney(q.data.ledger_balance, q.data.currency)}
              </p>
              <dl className="grid gap-x-8 gap-y-1 text-sm sm:grid-cols-2">
                <div>
                  <dt className="inline text-text-muted">Customer: </dt>
                  <dd className="inline">
                    <Link
                      href={`/s/${sessionId}/customers/${q.data.customer_id}`}
                      className="font-medium text-bank-primary hover:underline"
                    >
                      {q.data.customer_name}
                    </Link>{" "}
                    <span className="font-mono text-xs text-text-muted">
                      CIF {formatCif(q.data.cif_no)}
                    </span>
                  </dd>
                </div>
                <div><dt className="inline text-text-muted">Product: </dt><dd className="inline">{q.data.product_code} ({q.data.product_kind})</dd></div>
                <div><dt className="inline text-text-muted">Currency: </dt><dd className="inline">{q.data.currency}</dd></div>
                <div><dt className="inline text-text-muted">Mandate: </dt><dd className="inline">{mandateLabel(q.data.mandate)}</dd></div>
                <div><dt className="inline text-text-muted">Opened: </dt><dd className="inline">{formatDateTime(q.data.opened_at)}</dd></div>
                {q.data.closed_at && (
                  <div><dt className="inline text-text-muted">Closed: </dt><dd className="inline">{formatDateTime(q.data.closed_at)}</dd></div>
                )}
              </dl>
            </div>
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
          </section>

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
