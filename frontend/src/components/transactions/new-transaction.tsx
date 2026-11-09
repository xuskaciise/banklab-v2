"use client";

import { useState } from "react";
import Link from "next/link";
import { useSessionMe } from "@/lib/lab";
import { useMyTellerSession } from "@/lib/tellers";
import type { TransactionOut } from "@/lib/api/types";
import { EmptyState } from "@/components/shared/empty-state";
import { Button } from "@/components/ui/button";
import {
  PageHeader,
  QueryState,
  ReadOnlyBanner,
  Tabs,
} from "@/components/lab/common";
import { TxnForm, type Kind } from "./txn-form";
import { TxnResult } from "./txn-result";

const PERM: Record<Kind, string> = {
  deposit: "txn.cash_deposit",
  withdrawal: "txn.cash_withdrawal",
  transfer: "txn.transfer",
};
const LABEL: Record<Kind, string> = {
  deposit: "Cash deposit",
  withdrawal: "Cash withdrawal",
  transfer: "Transfer",
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
        <Tabs
          tabs={kinds.map((k) => ({ id: k, label: LABEL[k] }))}
          value={kind}
          onChange={(k) => setTab(k as Kind)}
        />
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
          !readOnly && <TxnForm key={kind} sid={sid} kind={kind} onDone={setResult} />
        )}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title="New transaction" subtitle="Post a customer transaction." />
      <QueryState query={me}>
        {readOnly && <ReadOnlyBanner />}
        {body}
      </QueryState>
    </div>
  );
}
