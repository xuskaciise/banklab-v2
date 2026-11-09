"use client";

import Link from "next/link";
import {
  ArrowRight,
  BookUser,
  ClipboardCheck,
  Landmark,
  Receipt,
  Repeat,
  Store,
  Wallet,
  WalletCards,
  type LucideIcon,
} from "lucide-react";
import { QUICK_ACTIONS } from "@/lib/role-guide";

const ICON: Record<string, LucideIcon> = {
  "New transaction": Repeat,
  "My till": Wallet,
  Approvals: ClipboardCheck,
  Tills: Store,
  Transactions: Receipt,
  Customers: BookUser,
  Accounts: WalletCards,
  Vault: Landmark,
};

/** Link cards for the screens this role can use; badges only where a count exists. */
export function QuickActions({
  sid,
  has,
  counts,
}: {
  sid: string;
  has: (c: string) => boolean;
  counts: Record<string, number>;
}) {
  const actions = QUICK_ACTIONS.filter((a) => a.any.some(has));
  if (!actions.length) return null;
  return (
    <section aria-label="Quick actions" className="space-y-2">
      <h2 className="text-sm font-semibold text-text-strong">Quick actions</h2>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {actions.map((a) => {
          const Icon = ICON[a.title] ?? ArrowRight;
          const n = counts[a.title];
          return (
            <Link
              key={a.title}
              href={a.href(sid)}
              className="group relative flex flex-col gap-1.5 rounded-xl border border-border bg-card p-3.5 shadow-xs transition-all outline-none hover:-translate-y-0.5 hover:border-bank-accent hover:shadow-md focus-visible:ring-2 focus-visible:ring-bank-accent motion-reduce:transition-none motion-reduce:hover:translate-y-0"
            >
              <span className="flex items-center justify-between">
                <span className="flex size-8 items-center justify-center rounded-full bg-bank-sky-light text-bank-primary">
                  <Icon className="size-4" aria-hidden />
                </span>
                <span className="flex items-center gap-2">
                  {n > 0 && (
                    <span className="rounded-full bg-fin-pending-bg px-2 py-0.5 text-xs font-semibold text-fin-pending tabular-nums">
                      {n}
                    </span>
                  )}
                  <ArrowRight
                    className="size-4 text-text-muted transition-transform group-hover:translate-x-0.5"
                    aria-hidden
                  />
                </span>
              </span>
              <span className="text-sm font-semibold text-text-strong">{a.title}</span>
              <span className="line-clamp-2 text-xs text-text-muted">{a.text}</span>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
