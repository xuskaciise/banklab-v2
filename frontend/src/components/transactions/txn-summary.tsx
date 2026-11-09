"use client";

import { ArrowRight, Info, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatAccountNo } from "@/lib/accounts";
import { formatMoney } from "@/lib/banking";
import { LIMIT_NOTE } from "@/lib/role-guide";
import type { AccountOut } from "@/lib/api/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { KIND_META, type Kind } from "./type-selector";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 py-2 text-sm">
      <dt className="text-text-muted">{label}</dt>
      <dd className="text-right font-medium text-text-strong">{children}</dd>
    </div>
  );
}

/** Live summary of what is being entered; the amount is shown as typed. */
export function TxnSummary({
  kind,
  from,
  to,
  amount,
  amountValid,
  dateLabel,
}: {
  kind: Kind;
  from: AccountOut | null;
  to: AccountOut | null;
  amount: string;
  amountValid: boolean;
  dateLabel: string;
}) {
  const tone =
    kind === "deposit"
      ? "text-fin-success"
      : kind === "withdrawal"
        ? "text-fin-danger"
        : "text-text-strong";
  return (
    <div className="space-y-4 lg:sticky lg:top-4">
      <Card>
        <CardHeader>
          <CardTitle>Transaction Summary</CardTitle>
        </CardHeader>
        <CardContent>
          {!from ? (
            <p className="rounded-lg bg-surface p-4 text-center text-sm text-text-muted">
              Find an account to see the transaction summary.
            </p>
          ) : (
            <dl className="divide-y divide-border">
              <Row label="Type">{KIND_META[kind].label}</Row>
              {kind === "transfer" ? (
                <div className="py-2 text-sm">
                  <div className="flex items-center gap-2">
                    <div className="min-w-0 flex-1">
                      <p className="text-xs text-text-muted">From</p>
                      <p className="truncate font-medium text-fin-danger">
                        {from.customer_name}
                      </p>
                      <p className="font-mono text-xs text-text-muted">
                        {formatAccountNo(from.account_no)}
                      </p>
                    </div>
                    <ArrowRight
                      className="size-4 shrink-0 text-text-muted"
                      aria-hidden
                    />
                    <div className="min-w-0 flex-1 text-right">
                      <p className="text-xs text-text-muted">To</p>
                      {to ? (
                        <>
                          <p className="truncate font-medium text-fin-success">
                            {to.customer_name}
                          </p>
                          <p className="font-mono text-xs text-text-muted">
                            {formatAccountNo(to.account_no)}
                          </p>
                        </>
                      ) : (
                        <p className="text-text-muted">Not selected</p>
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <>
                  <Row label="Customer">{from.customer_name}</Row>
                  <Row label="Account No">
                    <span className="font-mono">
                      {formatAccountNo(from.account_no)}
                    </span>
                  </Row>
                </>
              )}
              <Row label="Currency">{from.currency}</Row>
              <Row label="Amount">
                <span className={cn("text-lg font-semibold tabular-nums", tone)}>
                  {amountValid ? formatMoney(amount.trim(), from.currency) : "--"}
                </span>
              </Row>
              <Row label="Date">{dateLabel}</Row>
            </dl>
          )}
        </CardContent>
      </Card>
      <div className="flex gap-3 rounded-xl border border-border bg-surface p-4 text-sm text-text-muted">
        <ShieldCheck
          className="mt-0.5 size-4 shrink-0 text-bank-primary"
          aria-hidden
        />
        <div className="space-y-1.5">
          <p className="font-medium text-text-strong">Banking Reminder</p>
          <p>
            Please verify the account information and transaction amount before
            submitting.
          </p>
          <p className="flex gap-1.5 text-xs">
            <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
            {LIMIT_NOTE}
          </p>
        </div>
      </div>
    </div>
  );
}
