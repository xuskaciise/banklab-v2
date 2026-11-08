"use client";

import { useParams } from "next/navigation";
import { useSessionMe } from "@/lib/lab";
import { CustomersList } from "@/components/customers/customers-list";
import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader, QueryState, ReadOnlyBanner } from "@/components/lab/common";

export default function CustomersPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const me = useSessionMe(sessionId);
  const perms = new Set(me.data?.permissions.map((p) => p.code));
  const readOnly = !!me.data?.read_only;
  return (
    <div className="space-y-6">
      <PageHeader
        title="Customers"
        subtitle="Customer information files (CIF) of your bank."
      />
      <QueryState query={me}>
        {readOnly && <ReadOnlyBanner />}
        {!perms.has("customer.view") ? (
          <EmptyState title="No access" description="Your role cannot view customers." />
        ) : (
          <CustomersList
            scope={{ kind: "student", sessionId }}
            hrefFor={(id) => `/s/${sessionId}/customers/${id}`}
            newHref={
              perms.has("customer.create") && !readOnly
                ? `/s/${sessionId}/customers/new`
                : undefined
            }
          />
        )}
      </QueryState>
    </div>
  );
}
