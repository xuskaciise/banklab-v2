"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { BookOpen, ChevronRight } from "lucide-react";
import { useSessionMe } from "@/lib/lab";
import { REPORTS } from "@/lib/reports";
import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader, QueryState } from "@/components/lab/common";

function Card({ href, title, description }: { href: string; title: string; description: string }) {
  return (
    <Link
      href={href}
      className="group flex items-start justify-between gap-3 rounded-xl border border-border bg-card p-4 shadow-xs transition-colors outline-none hover:border-bank-accent focus-visible:ring-2 focus-visible:ring-bank-accent"
    >
      <div>
        <p className="font-medium text-text-strong">{title}</p>
        <p className="mt-1 text-sm text-text-muted">{description}</p>
      </div>
      <ChevronRight className="mt-0.5 size-4 shrink-0 text-text-muted group-hover:text-bank-accent" />
    </Link>
  );
}

export default function ReportsIndexPage() {
  const { sessionId: sid } = useParams<{ sessionId: string }>();
  const me = useSessionMe(sid);
  const perms = new Set(me.data?.permissions.map((p) => p.code));
  const items = REPORTS.filter((r) => perms.has(r.perm));
  const gl = perms.has("gl.view");
  return (
    <div>
      <PageHeader title="Reports" subtitle="Financial and operational reports for your bank." />
      <QueryState query={me}>
        {items.length === 0 && !gl ? (
          <EmptyState
            icon={BookOpen}
            title="No reports available"
            description={
              perms.has("account.statement")
                ? "Open an account to print its statement."
                : "Your role has no reports."
            }
          />
        ) : (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {items.map((r) => (
              <Card key={r.slug} href={`/s/${sid}/reports/${r.slug}`} title={r.title} description={r.description} />
            ))}
            {gl && (
              <Card
                href={`/s/${sid}/gl`}
                title="General ledger"
                description="Chart of accounts; open an account for its ledger lines."
              />
            )}
          </div>
        )}
        {perms.has("account.statement") && items.length + (gl ? 1 : 0) > 0 && (
          <p className="mt-4 text-sm text-text-muted">
            Account statements are printed from the account page.
          </p>
        )}
      </QueryState>
    </div>
  );
}
