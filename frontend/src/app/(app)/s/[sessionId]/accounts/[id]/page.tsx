"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { useSessionMe } from "@/lib/lab";
import { buttonVariants } from "@/components/ui/button";
import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader, QueryState, ReadOnlyBanner } from "@/components/lab/common";
import { AccountDetailView } from "@/components/accounts/account-detail";

export default function AccountDetailPage() {
  const { sessionId, id } = useParams<{ sessionId: string; id: string }>();
  const me = useSessionMe(sessionId);
  const perms = new Set(me.data?.permissions.map((p) => p.code));
  const readOnly = !!me.data?.read_only;
  return (
    <div className="space-y-6">
      <PageHeader
        title="Account"
        actions={
          <Link
            href={`/s/${sessionId}/accounts`}
            className={buttonVariants({ variant: "outline" })}
          >
            <ArrowLeft /> Accounts
          </Link>
        }
      />
      <QueryState query={me}>
        {readOnly && <ReadOnlyBanner />}
        {!perms.has("account.view") ? (
          <EmptyState title="No access" description="Your role cannot view accounts." />
        ) : (
          <AccountDetailView
            sessionId={sessionId}
            id={id}
            canClose={perms.has("account.close") && !readOnly}
            canIssueChequebook={perms.has("chequebook.issue") && !readOnly}
            canStopCheque={perms.has("cheque.stop") && !readOnly}
          />
        )}
      </QueryState>
    </div>
  );
}
