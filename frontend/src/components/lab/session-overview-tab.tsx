"use client";

import {
  Activity,
  Building2,
  CalendarDays,
  ChevronRight,
  Eye,
  GraduationCap,
  Landmark,
  Layers,
  PanelRight,
  ShieldCheck,
  Users,
} from "lucide-react";
import type { SessionOut } from "@/lib/api/types";
import {
  BANK_ROLES,
  ROLE_LABEL,
  formatDateTime,
  useBanks,
  useBusinessDays,
  useMembers,
} from "@/lib/lab";
import { cn } from "@/lib/utils";
import { FormSection } from "@/components/shared/form-layout";
import { StatCard } from "@/components/shared/stat-card";
import { StatusBadge } from "@/components/shared/status-badge";
import { formatTemplateLabel } from "./common";

type Icon = React.ComponentType<{ className?: string }>;

function Fact({
  icon: I,
  label,
  children,
}: {
  icon: Icon;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-3">
      <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-surface text-bank-primary">
        <I className="size-4" aria-hidden />
      </span>
      <div className="min-w-0">
        <dt className="text-xs text-text-muted">{label}</dt>
        <dd className="text-sm font-medium text-text-strong">{children}</dd>
      </div>
    </div>
  );
}

const readable = (iso: string) => {
  const d = new Date(`${iso}T00:00:00`);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString(undefined, {
        weekday: "short",
        day: "numeric",
        month: "short",
        year: "numeric",
      });
};

const SHORTCUTS: { id: string; label: string; icon: Icon }[] = [
  { id: "members", label: "Members", icon: Users },
  { id: "banks", label: "Banks", icon: Landmark },
  { id: "permissions", label: "Permissions", icon: ShieldCheck },
  { id: "activity", label: "Activity", icon: Activity },
];

export function OverviewTab({
  session,
  onNavigate,
}: {
  session: SessionOut;
  onNavigate?: (tab: string) => void;
}) {
  const members = useMembers(session.id);
  const banks = useBanks(session.id);
  const days = useBusinessDays(session.id);
  const hasDays = !!days.data?.length;

  return (
    <div className="space-y-6">
      <div
        className={cn(
          "grid gap-4 sm:grid-cols-2",
          hasDays ? "lg:grid-cols-4" : "lg:grid-cols-3",
        )}
      >
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
        <StatCard
          label="Status"
          icon={Activity}
          value={<StatusBadge status={session.status} className="h-7 px-3 text-sm" />}
          hint={
            session.status === "draft"
              ? "Open it from the Settings tab."
              : `Opened ${formatDateTime(session.opened_at)}`
          }
        />
        {hasDays && (
          <StatCard
            label="Business days"
            icon={CalendarDays}
            value={days.data?.length}
            hint="One current day per bank"
          />
        )}
      </div>

      {onNavigate && (
        <nav aria-label="Quick actions" className="flex flex-wrap gap-2">
          {SHORTCUTS.map(({ id, label, icon: I }) => (
            <button
              key={id}
              type="button"
              onClick={() => onNavigate(id)}
              className="inline-flex h-9 items-center gap-2 rounded-lg border border-border bg-card px-3 text-sm font-medium text-text-body transition-colors outline-none hover:border-bank-accent hover:bg-bank-sky-light focus-visible:ring-2 focus-visible:ring-bank-accent"
            >
              <I className="size-4 text-bank-primary" aria-hidden />
              {label}
            </button>
          ))}
        </nav>
      )}

      <div className="grid items-start gap-6 lg:grid-cols-2">
        <FormSection title="Configuration">
          <dl className="grid gap-4 sm:grid-cols-2">
            <Fact icon={GraduationCap} label="Kind">
              <span className="capitalize">{session.kind}</span>
            </Fact>
            <Fact icon={Layers} label="Structure">
              {formatTemplateLabel(session.structure)}
            </Fact>
            <Fact icon={Eye} label="Default visibility">
              {session.default_visibility === "own" ? "Own work only" : "Whole bank"}
            </Fact>
            <Fact icon={PanelRight} label="Dr/Cr learning panel">
              {session.learning_panel ? "On" : "Off"}
            </Fact>
          </dl>
          <div className="border-t border-border pt-4">
            <p className="text-xs text-text-muted">
              Allowed roles ({session.allowed_roles.length} of {BANK_ROLES.length})
            </p>
            <ul className="mt-2 flex flex-wrap justify-start gap-1.5">
              {session.allowed_roles.map((r) => (
                <li
                  key={r}
                  className="rounded-full bg-bank-sky-light px-2.5 py-0.5 text-xs font-medium text-bank-primary"
                >
                  {ROLE_LABEL[r] ?? r}
                </li>
              ))}
            </ul>
          </div>
        </FormSection>

        <FormSection title="Business date per bank">
          {hasDays ? (
            <ul className="-my-2 divide-y divide-border">
              {days.data?.map((d) => (
                <li
                  key={d.bank_id}
                  className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm"
                >
                  <span className="font-medium text-text-strong">{d.bank_name}</span>
                  <span className="flex items-center gap-3">
                    <time
                      dateTime={d.date}
                      title={d.date}
                      className="text-text-body tabular-nums"
                    >
                      {readable(d.date)}
                    </time>
                    <StatusBadge status={d.status} />
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="rounded-lg bg-surface px-4 py-3 text-sm text-text-muted">
              {days.isPending
                ? "Loading…"
                : "Business days appear once the session is open."}
            </p>
          )}
          {onNavigate && hasDays && (
            <button
              type="button"
              onClick={() => onNavigate("banks")}
              className="inline-flex items-center gap-1 rounded text-sm font-medium text-bank-primary outline-none hover:underline focus-visible:ring-2 focus-visible:ring-bank-accent"
            >
              Manage banks <ChevronRight className="size-4" aria-hidden />
            </button>
          )}
        </FormSection>
      </div>
    </div>
  );
}
