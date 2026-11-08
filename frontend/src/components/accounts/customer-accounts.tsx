"use client";

import { useState } from "react";
import Link from "next/link";
import { Plus } from "lucide-react";
import { formatAccountNo, statusLabel, useAccounts } from "@/lib/accounts";
import { formatMoney } from "@/lib/banking";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/shared/status-badge";
import { ErrorMsg, Loading, Table, Td, Th } from "@/components/lab/common";
import { OpenAccountDialog } from "@/components/accounts/open-account-dialog";

export function CustomerAccounts({
  sessionId,
  customerId,
  canOpen,
}: {
  sessionId: string;
  customerId: string;
  canOpen: boolean;
}) {
  const list = useAccounts(sessionId, { customerId });
  const [opening, setOpening] = useState(false);
  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-text-strong">
          Accounts{list.data ? ` (${list.data.count})` : ""}
        </h2>
        {canOpen && (
          <Button onClick={() => setOpening(true)}>
            <Plus /> Open account
          </Button>
        )}
      </div>
      {list.isPending ? (
        <Loading label="Loading accounts" />
      ) : list.isError ? (
        <ErrorMsg error={list.error} />
      ) : list.data.items.length === 0 ? (
        <p className="text-sm text-text-muted">No accounts yet.</p>
      ) : (
        <Table>
          <thead>
            <tr>
              <Th>Account no</Th>
              <Th>Product</Th>
              <Th className="text-right">Balance</Th>
              <Th>Status</Th>
            </tr>
          </thead>
          <tbody>
            {list.data.items.map((a) => (
              <tr key={a.id} className="hover:bg-hover">
                <Td className="font-mono text-xs">
                  <Link
                    href={`/s/${sessionId}/accounts/${a.id}`}
                    className="font-medium text-bank-primary hover:underline"
                  >
                    {formatAccountNo(a.account_no)}
                  </Link>
                </Td>
                <Td>{a.product_name}</Td>
                <Td className="text-right font-medium whitespace-nowrap text-text-strong tabular-nums">
                  {formatMoney(a.ledger_balance, a.currency)}
                </Td>
                <Td>
                  <StatusBadge status={a.status} label={statusLabel(a.status)} />
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
      {opening && (
        <OpenAccountDialog
          sessionId={sessionId}
          customerId={customerId}
          onClose={() => setOpening(false)}
        />
      )}
    </section>
  );
}
