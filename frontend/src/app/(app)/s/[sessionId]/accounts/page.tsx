"use client";

import { useParams } from "next/navigation";
import { useSessionMe } from "@/lib/lab";
import { AccountsList } from "@/components/accounts/accounts-list";
import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader, QueryState, ReadOnlyBanner } from "@/components/lab/common";

export default function AccountsPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const me = useSessionMe(sessionId);
  const perms = new Set(me.data?.permissions.map((p) => p.code));
  const readOnly = !!me.data?.read_only;
  return (
    <div className="space-y-6">
      <PageHeader title="Accounts" subtitle="Customer accounts of your bank." />
      <QueryState query={me}>
        {readOnly && <ReadOnlyBanner />}
        {!perms.has("account.view") ? (
          <EmptyState title="No access" description="Your role cannot view accounts." />
        ) : (
          <AccountsList
            sessionId={sessionId}
            canOpen={perms.has("account.open") && !readOnly}
          />
        )}
      </QueryState>
    </div>
  );
}
