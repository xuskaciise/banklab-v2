"use client";

import Link from "next/link";
import { CheckCircle2 } from "lucide-react";
import { relativeTime } from "@/lib/lab";
import { Button } from "@/components/ui/button";
import type { PendingItem } from "./use-pending";

/** Latest five items waiting for a decision, with a Review link each. */
export function PendingPreview({
  items,
  loading,
  viewAll,
}: {
  items: PendingItem[];
  loading: boolean;
  viewAll: string;
}) {
  const top = items.slice(0, 5);
  return (
    <section className="rounded-xl border border-border bg-card p-4 shadow-xs">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-text-strong">Pending approvals</h2>
        {items.length > 0 && (
          <Link
            href={viewAll}
            className="rounded text-xs font-medium text-bank-primary outline-none hover:underline focus-visible:ring-2 focus-visible:ring-bank-accent"
          >
            View all ({items.length})
          </Link>
        )}
      </div>
      {loading ? (
        <p className="py-4 text-center text-sm text-text-muted">Loading…</p>
      ) : top.length === 0 ? (
        <p className="flex items-center justify-center gap-2 rounded-lg bg-surface py-5 text-sm text-text-muted">
          <CheckCircle2 className="size-4 text-fin-success" aria-hidden />
          No pending approvals — you&apos;re all caught up
        </p>
      ) : (
        <ul className="divide-y divide-border">
          {top.map((i) => (
            <li key={i.key} className="flex items-center gap-3 py-2">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-text-strong">{i.title}</p>
                <p className="truncate text-xs text-text-muted">
                  {i.sub} · {relativeTime(i.at)}
                </p>
              </div>
              {i.amount && (
                <span className="text-sm font-semibold text-text-strong tabular-nums">
                  {i.amount}
                </span>
              )}
              <Button size="sm" variant="outline" render={<Link href={i.href} />}>
                Review
              </Button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
