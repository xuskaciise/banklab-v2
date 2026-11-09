import { CheckCircle2, XCircle } from "lucide-react";
import { StatusBadge } from "@/components/shared/status-badge";
import { CheckItems } from "@/components/eod/check-items";
import type { EodCheck } from "@/lib/api/types";

export function CheckCard({ check, sid }: { check: EodCheck; sid: string }) {
  const Icon = check.ok ? CheckCircle2 : XCircle;
  return (
    <li className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-start gap-3">
        <Icon
          aria-hidden
          className={`mt-0.5 size-5 shrink-0 ${check.ok ? "text-fin-success" : "text-fin-danger"}`}
        />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-text-strong">{check.label}</h2>
            <StatusBadge
              status={check.ok ? "completed" : "failed"}
              label={check.ok ? "Passed" : "Needs attention"}
            />
          </div>
          <p className="mt-1 text-sm text-text-muted">{check.detail}</p>
          <CheckItems check={check} sid={sid} />
        </div>
      </div>
    </li>
  );
}
