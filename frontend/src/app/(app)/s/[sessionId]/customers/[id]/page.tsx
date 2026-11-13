"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { useSessionMe } from "@/lib/lab";
import { buttonVariants } from "@/components/ui/button";
import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader, QueryState, ReadOnlyBanner } from "@/components/lab/common";
import { CustomerDetailView } from "@/components/customers/customer-detail";

export default function CustomerDetailPage() {
  const { sessionId, id } = useParams<{ sessionId: string; id: string }>();
  const me = useSessionMe(sessionId);
  const perms = new Set(me.data?.permissions.map((p) => p.code));
  const readOnly = !!me.data?.read_only;
  return (
    <div className="space-y-6">
      <PageHeader
        title="Customer"
        actions={
          <Link
            href={`/s/${sessionId}/customers`}
            className={buttonVariants({ variant: "outline" })}
          >
            <ArrowLeft /> Customers
          </Link>
        }
      />
      <QueryState query={me}>
        {readOnly && <ReadOnlyBanner />}
        {!perms.has("customer.view") ? (
          <EmptyState title="No access" description="Your role cannot view customers." />
        ) : (
          <CustomerDetailView
            scope={{ kind: "student", sessionId }}
            id={id}
            canEdit={perms.has("customer.update") && !readOnly}
            accounts={
              perms.has("account.view")
                ? { canOpen: perms.has("account.open") && !readOnly }
                : undefined
            }
          />
        )}
      </QueryState>
    </div>
  );
}
