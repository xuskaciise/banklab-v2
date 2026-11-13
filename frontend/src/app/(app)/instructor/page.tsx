"use client";

import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  GraduationCap,
  PlayCircle,
  PlusCircle,
  RefreshCw,
  Upload,
  Users,
} from "lucide-react";
import { useStaffDashboard } from "@/lib/dashboard";
import { actionLabel, formatDateTime, useClasses } from "@/lib/lab";
import { useMe } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { StatCard } from "@/components/shared/stat-card";
import { StatusBadge } from "@/components/shared/status-badge";
import { ClassPickerMenu } from "@/components/lab/class-picker-menu";
import { CreateClassDialog } from "@/components/lab/create-class-dialog";
import { ErrorMsg } from "@/components/lab/common";

function Panel({
  title,
  action,
  children,
}: {
  title: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="overflow-hidden rounded-xl border border-border bg-card shadow-xs">
      <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold text-text-strong">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function RowsSkeleton() {
  return (
    <div className="space-y-3 p-4" role="status" aria-label="Loading">
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} className="h-5 w-full" />
      ))}
    </div>
  );
}

export default function StaffOverviewPage() {
  const qc = useQueryClient();
  const { data: user } = useMe();
  const classes = useClasses();
  const classList = classes.data;
  const dash = useStaffDashboard();
  const dd = dash.data;

  const loadingClasses = classes.isPending;
  const fetching = classes.isFetching || dash.isFetching;

  function refresh() {
    qc.invalidateQueries({ queryKey: ["classes"] });
    qc.invalidateQueries({ queryKey: ["class-sessions"] });
    qc.invalidateQueries({ queryKey: ["students"] });
    qc.invalidateQueries({ queryKey: ["staff-dashboard"] });
  }

  const firstName = user?.full_name?.split(" ")[0];

  return (
    <div className="space-y-6">
      <PageHeader
        className="mb-0"
        title={firstName ? `Welcome back, ${firstName}` : "Overview"}
        subtitle="A summary of your classes, students and sessions."
        actions={
          <Button variant="outline" onClick={refresh} disabled={fetching}>
            <RefreshCw className={fetching ? "animate-spin" : undefined} />
            Refresh
          </Button>
        }
      />

      <ErrorMsg error={classes.error} />

      <ErrorMsg error={dash.error} />

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          label="Classes"
          icon={GraduationCap}
          loading={dash.isPending}
          value={dd?.counts.classes ?? 0}
          hint="Classes you teach"
        />
        <StatCard
          label="Students"
          icon={Users}
          loading={dash.isPending}
          value={dd?.counts.students ?? 0}
          hint="Enrolled across your classes"
        />
        <StatCard
          label="Active sessions"
          icon={PlayCircle}
          loading={dash.isPending}
          value={dd?.counts.active_sessions ?? 0}
          hint="Open for students now"
        />
      </div>

      <Panel
        title="Active sessions"
        action={
          <Link
            href="/instructor/classes"
            className="text-xs font-medium text-bank-accent hover:underline"
          >
            View classes
          </Link>
        }
      >
        {dash.isPending ? (
          <RowsSkeleton />
        ) : dd?.sessions.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-surface text-xs text-text-muted uppercase">
                <tr>
                  <th scope="col" className="px-4 py-2 text-left font-medium">Session</th>
                  <th scope="col" className="px-3 py-2 text-left font-medium">Kind</th>
                  <th scope="col" className="px-3 py-2 text-left font-medium">Dr/Cr panel</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">Banks</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">Members</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">Txns today</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">Pending</th>
                  <th scope="col" className="px-4 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {dd.sessions.map((s) => (
                  <tr key={s.id} className="hover:bg-hover">
                    <td className="px-4 py-2.5">
                      <span className="block font-medium text-text-strong">{s.name}</span>
                      <span className="block text-xs text-text-muted">{s.class_name}</span>
                    </td>
                    <td className="px-3 py-2.5 capitalize">{s.kind}</td>
                    <td className="px-3 py-2.5">
                      <StatusBadge
                        status={s.learning_panel ? "active" : "inactive"}
                        label={s.learning_panel ? "On" : "Off"}
                      />
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{s.banks_count}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{s.members_count}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{s.today_transactions}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums">
                      {s.pending_approvals > 0 ? (
                        <span className="font-semibold text-fin-pending">{s.pending_approvals}</span>
                      ) : (
                        0
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <Link href={`/instructor/sessions/${s.id}`}>
                        <Button size="sm" variant="outline">
                          Control
                        </Button>
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            className="rounded-none border-0"
            title="No active sessions"
            description="Open a session from one of your classes to start a lab."
          />
        )}
      </Panel>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Panel
            title="My classes"
            action={
              <Link
                href="/instructor/classes"
                className="text-xs font-medium text-bank-accent hover:underline"
              >
                See all
              </Link>
            }
          >
            {loadingClasses ? (
              <RowsSkeleton />
            ) : classList?.length ? (
              <ul className="divide-y divide-border">
                {classList.map((c) => (
                  <li key={c.id}>
                    <Link
                      href={`/instructor/classes/${c.id}`}
                      className="flex items-center justify-between gap-3 px-4 py-3 transition-colors hover:bg-hover"
                    >
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-medium text-text-strong">
                          {c.name}
                        </span>
                        <span className="block font-mono text-xs text-text-muted">
                          {c.code}
                        </span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState
                className="rounded-none border-0"
                title="No classes yet"
                description="Create your first class to get started."
                action={<CreateClassDialog label="Create class" />}
              />
            )}
          </Panel>

          <Panel title="Recent activity">
            {dash.isPending ? (
              <RowsSkeleton />
            ) : dd?.recent_activity.length ? (
              <ul className="divide-y divide-border">
                {dd.recent_activity.map((a) => (
                  <li key={a.id} className="flex gap-3 px-4 py-2.5">
                    <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-bank-sky-light text-bank-primary">
                      <Activity className="size-3.5" />
                    </span>
                    <div className="min-w-0 text-sm">
                      <p className="truncate font-medium text-text-strong">
                        {actionLabel(a.action)}
                      </p>
                      <p className="truncate text-xs text-text-muted">
                        {a.actor_name ?? "system"}
                        {a.bank_name ? ` · ${a.bank_name}` : ""}
                        {a.session_name ? ` · ${a.session_name}` : ""}
                        {` · ${formatDateTime(a.at)}`}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState
                className="rounded-none border-0"
                title="No activity yet"
                description="Actions in your sessions will appear here."
              />
            )}
          </Panel>
        </div>

        <div className="space-y-6">
          <Panel title="Quick actions">
            <div className="space-y-2 p-4">
              <CreateClassDialog label="New class" />
              <ClassPickerMenu
                label="New session"
                icon={<PlusCircle className="size-4" />}
                classes={classList}
                hrefFor={(c) => `/instructor/sessions/new?classId=${c.id}`}
              />
              <ClassPickerMenu
                label="Import students"
                icon={<Upload className="size-4" />}
                classes={classList}
                hrefFor={(c) => `/instructor/classes/${c.id}/import`}
              />
              {!loadingClasses && !classList?.length && (
                <p className="text-xs text-text-muted">
                  Create a class first to enable these actions.
                </p>
              )}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
