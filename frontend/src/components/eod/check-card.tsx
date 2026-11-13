"use client";

import { useState } from "react";
import Link from "next/link";
import { CheckCircle2, ChevronDown, Loader2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { StatusBadge } from "@/components/shared/status-badge";
import { CheckItems } from "@/components/eod/check-items";
import type { EodCheck } from "@/lib/api/types";

const FIX: Record<string, { href: string; label: string }> = {
  teller_sessions_closed: { href: "tills", label: "Go to tills" },
  no_pending_approvals: { href: "approvals", label: "View pending approvals" },
  cash_reconciliation: { href: "vault", label: "Go to vault" },
};

export function CheckRow({
  check,
  sid,
  running,
  last,
}: {
  check: EodCheck;
  sid: string;
  running: boolean;
  last: boolean;
}) {
  const [open, setOpen] = useState(true);
  const failed = !check.ok && !running;
  const fix = FIX[check.code];
  const expandable = failed && check.items.length > 0;
  const Icon = check.ok ? CheckCircle2 : XCircle;

  return (
    <li className={cn("relative flex gap-3 px-5 py-4", failed && "bg-fin-danger-bg/40")}>
      {!last && <span aria-hidden className="absolute top-11 -bottom-2 left-[29px] w-px bg-border" />}
      <span className="relative z-10 mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-card">
        {running ? (
          <Loader2 aria-hidden className="size-5 animate-spin text-bank-accent" />
        ) : (
          <Icon aria-hidden className={cn("size-5", check.ok ? "text-fin-success" : "text-fin-danger")} />
        )}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-text-strong">{check.label}</h3>
          <div className="flex items-center gap-2">
            {running ? (
              <StatusBadge status="running" label="Running" tone="info" />
            ) : (
              <StatusBadge status={check.ok ? "completed" : "failed"} label={check.ok ? "Passed" : "Failed"} />
            )}
            {expandable && (
              <button
                type="button"
                aria-expanded={open}
                aria-label={`${open ? "Hide" : "Show"} details for ${check.label}`}
                onClick={() => setOpen((o) => !o)}
                className="inline-flex size-7 items-center justify-center rounded-md text-text-muted outline-none hover:bg-hover focus-visible:ring-2 focus-visible:ring-bank-accent"
              >
                <ChevronDown aria-hidden className={cn("size-4 transition-transform", open && "rotate-180")} />
              </button>
            )}
          </div>
        </div>
        <p className="mt-0.5 text-sm text-text-muted">{running ? "Checking…" : check.detail}</p>
        {failed && open && <CheckItems check={check} sid={sid} />}
        {failed && fix && (
          <Link
            href={`/s/${sid}/${fix.href}`}
            className="mt-3 inline-flex h-8 items-center rounded-md border border-border bg-card px-3 text-sm font-medium text-bank-primary outline-none hover:bg-hover focus-visible:ring-2 focus-visible:ring-bank-accent"
          >
            {fix.label}
          </Link>
        )}
      </div>
    </li>
  );
}
