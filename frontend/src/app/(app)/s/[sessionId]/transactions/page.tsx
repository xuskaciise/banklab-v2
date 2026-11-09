"use client";

import { useParams } from "next/navigation";
import { useSessionMe } from "@/lib/lab";
import { TxnsList } from "@/components/transactions/txns-list";
import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader, QueryState, ReadOnlyBanner } from "@/components/lab/common";

export default function TransactionsPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const me = useSessionMe(sessionId);
  const perms = new Set(me.data?.permissions.map((p) => p.code));
  const readOnly = !!me.data?.read_only;
  return (
    <div className="space-y-6">
      <PageHeader title="Transactions" subtitle="Customer transactions of your bank." />
      <QueryState query={me}>
        {readOnly && <ReadOnlyBanner />}
        {!perms.has("report.operational") ? (
          <EmptyState title="No access" description="Your role cannot view transactions." />
        ) : (
          <TxnsList
            sid={sessionId}
            canReverse={perms.has("txn.reverse") && !readOnly}
          />
        )}
      </QueryState>
    </div>
  );
}
