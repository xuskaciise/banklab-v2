"use client";

import { useState } from "react";
import Link from "next/link";
import { useSessionMe } from "@/lib/lab";
import { useMyTellerSession } from "@/lib/tellers";
import type { TransactionOut } from "@/lib/api/types";
import { EmptyState } from "@/components/shared/empty-state";
import { Button } from "@/components/ui/button";
import { PageHeader, QueryState, ReadOnlyBanner } from "@/components/lab/common";
import { TxnForm } from "./txn-form";
import { TypeSelector, type Kind } from "./type-selector";
import { TxnResult } from "./txn-result";

const PERM: Record<Kind, string> = {
  deposit: "txn.cash_deposit",
  withdrawal: "txn.cash_withdrawal",
  transfer: "txn.transfer",
};

export function NewTransaction({ sid }: { sid: string }) {
  const me = useSessionMe(sid);
  const perms = new Set(me.data?.permissions.map((p) => p.code));
  const isTeller = perms.has("till.open.request");
  const till = useMyTellerSession(sid, isTeller);
  const kinds = (Object.keys(PERM) as Kind[]).filter((k) => perms.has(PERM[k]));
  const [tab, setTab] = useState<Kind | null>(null);
  const [result, setResult] = useState<TransactionOut | null>(null);
  const kind = tab && kinds.includes(tab) ? tab : kinds[0];
  const needsTill = !!kind && kind !== "transfer" && isTeller;
  const readOnly = !!me.data?.read_only;

  const bizDate = me.data?.business_date;
  const dateLabel = bizDate
    ? `${bizDate} (business date)`
    : `${new Date().toISOString().slice(0, 10)} (today)`;

  let body: React.ReactNode = null;
  if (!kind) {
    body = (
      <EmptyState title="No access" description="Your role cannot post transactions." />
    );
  } else if (result) {
    body = <TxnResult sid={sid} txn={result} onNew={() => setResult(null)} />;
  } else {
    body = (
      <div className="space-y-5">
        <TypeSelector kinds={kinds} value={kind} onChange={setTab} />
        {needsTill && till.isPending ? (
          <p className="text-sm text-text-muted">Checking your till…</p>
        ) : needsTill && till.data?.status !== "open" ? (
          <EmptyState
            title="Your till is not open"
            description="Cash transactions need an open till session."
            action={
              <Button render={<Link href={`/s/${sid}/teller/till`} />}>
                Go to my till
              </Button>
            }
          />
        ) : (
          !readOnly && (
            <TxnForm
              key={kind}
              sid={sid}
              kind={kind}
              dateLabel={dateLabel}
              onDone={setResult}
            />
          )
        )}
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6">
      <PageHeader
        title="New Transaction"
        subtitle="Process customer financial transactions securely."
        className="mb-0"
      />
      <QueryState query={me}>
        {readOnly && <ReadOnlyBanner />}
        {body}
      </QueryState>
    </div>
  );
}
