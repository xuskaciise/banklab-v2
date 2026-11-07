"use client";

import { Building2, Users } from "lucide-react";
import type { SessionOut } from "@/lib/api/types";
import {
  ROLE_LABEL,
  formatDateTime,
  useBanks,
  useBusinessDays,
  useMembers,
} from "@/lib/lab";
import { StatCard } from "@/components/shared/stat-card";
import { StatusBadge } from "@/components/shared/status-badge";
import { formatTemplateLabel } from "./common";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 py-2.5 text-sm">
      <dt className="text-text-muted">{label}</dt>
      <dd className="text-right font-medium text-text-strong">{children}</dd>
    </div>
  );
}

export function OverviewTab({ session }: { session: SessionOut }) {
  const members = useMembers(session.id);
  const banks = useBanks(session.id);
  const days = useBusinessDays(session.id);
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          label="Members"
          icon={Users}
          loading={members.isPending}
          value={members.data?.length ?? "—"}
          hint="Students in this session"
        />
        <StatCard
          label="Banks"
          icon={Building2}
          loading={banks.isPending}
          value={banks.data?.length ?? "—"}
          hint={session.structure === "per_group" ? "One per group" : "Single bank"}
        />
        <div className="rounded-xl border border-border bg-card p-4 shadow-xs">
          <p className="text-xs font-medium tracking-wide text-text-muted uppercase">
            Status
          </p>
          <div className="mt-3">
            <StatusBadge status={session.status} className="h-6 px-2.5 text-sm" />
          </div>
          <p className="mt-2 text-xs text-text-muted">
            {session.status === "draft"
              ? "Open it from the Settings tab."
              : `Opened ${formatDateTime(session.opened_at)}`}
          </p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-xl border border-border bg-card p-4 shadow-xs">
          <h2 className="text-sm font-semibold text-text-strong">Configuration</h2>
          <dl className="mt-2 divide-y divide-border">
            <Row label="Kind">
              <span className="capitalize">{session.kind}</span>
            </Row>
            <Row label="Structure">{formatTemplateLabel(session.structure)}</Row>
            <Row label="Default visibility">
              {session.default_visibility === "own" ? "Own work only" : "Whole bank"}
            </Row>
            <Row label="Dr/Cr learning panel">
              {session.learning_panel ? "On" : "Off"}
            </Row>
            <Row label="Allowed roles">
              <span className="flex flex-wrap justify-end gap-1">
                {session.allowed_roles.map((r) => (
                  <span
                    key={r}
                    className="rounded-full bg-bank-sky-light px-2 py-0.5 text-xs font-medium text-bank-primary"
                  >
                    {ROLE_LABEL[r] ?? r}
                  </span>
                ))}
              </span>
            </Row>
          </dl>
        </section>

        <section className="rounded-xl border border-border bg-card p-4 shadow-xs">
          <h2 className="text-sm font-semibold text-text-strong">
            Business date per bank
          </h2>
          {days.data?.length ? (
            <ul className="mt-2 divide-y divide-border">
              {days.data.map((d) => (
                <li
                  key={d.bank_id}
                  className="flex items-center justify-between gap-3 py-2.5 text-sm"
                >
                  <span className="font-medium text-text-strong">{d.bank_name}</span>
                  <span className="flex items-center gap-3">
                    <span className="text-text-muted tabular-nums">{d.date}</span>
                    <StatusBadge status={d.status} />
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-text-muted">
              {days.isPending
                ? "Loading…"
                : "Business days appear once the session is open."}
            </p>
          )}
        </section>
      </div>
    </div>
  );
}
