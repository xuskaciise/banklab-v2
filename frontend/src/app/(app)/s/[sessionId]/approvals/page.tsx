"use client";

import { useParams } from "next/navigation";
import { useSessionMe } from "@/lib/lab";
import { ApprovalsList } from "@/components/transactions/approvals-list";
import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader, QueryState, ReadOnlyBanner } from "@/components/lab/common";

export default function ApprovalsPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const me = useSessionMe(sessionId);
  const perms = new Set(me.data?.permissions.map((p) => p.code));
  const readOnly = !!me.data?.read_only;
  return (
    <div className="space-y-6">
      <PageHeader title="Approvals" subtitle="Transactions waiting for your decision." />
      <QueryState query={me}>
        {readOnly && <ReadOnlyBanner />}
        {!perms.has("approval.decide") ? (
          <EmptyState title="No access" description="Your role cannot decide approvals." />
        ) : (
          <ApprovalsList sid={sessionId} readOnly={readOnly} />
        )}
      </QueryState>
    </div>
  );
}
