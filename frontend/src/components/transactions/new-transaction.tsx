"use client";

import { useState } from "react";
import Link from "next/link";
import { useSessionMe } from "@/lib/lab";
import { useMyTellerSession } from "@/lib/tellers";
import type { TransactionOut } from "@/lib/api/types";
import { EmptyState } from "@/components/shared/empty-state";
import { Button } from "@/components/ui/button";
import { QueryState, ReadOnlyBanner } from "@/components/lab/common";
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
  const [formKey, setFormKey] = useState(0);
  // Any way of closing the result modal resets the form.
  const startNew = () => {
    setResult(null);
    setFormKey((k) => k + 1);
  };
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
  } else {
    body = (
      <>
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
              key={`${kind}-${formKey}`}
              sid={sid}
              kind={kind}
              dateLabel={dateLabel}
              onDone={setResult}
            />
          )
        )}
      </>
    );
  }

  // lg+: exactly viewport height minus the 56px (h-14) topbar; columns scroll inside.
  return (
    <div className="flex min-h-0 flex-col gap-3 p-4 lg:h-[calc(100dvh-3.5rem)] lg:overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <h1 className="text-lg font-semibold tracking-tight text-text-strong sm:text-xl">
            New Transaction
          </h1>
          <p className="text-xs text-text-muted">
            Process customer financial transactions securely.
          </p>
        </div>
        {kind && <TypeSelector kinds={kinds} value={kind} onChange={setTab} />}
      </div>
      <div className="flex min-h-0 flex-1 flex-col gap-3 lg:overflow-y-auto">
        <QueryState query={me}>
          {readOnly && <ReadOnlyBanner />}
          {body}
        </QueryState>
        {result && (
          <TxnResult
            sid={sid}
            txn={result}
            onNew={startNew}
            tillCode={isTeller ? till.data?.till_code : null}
          />
        )}
      </div>
    </div>
  );
}
