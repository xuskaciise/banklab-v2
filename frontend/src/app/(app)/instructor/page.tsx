"use client";

import Link from "next/link";
import { useQueries, useQueryClient } from "@tanstack/react-query";
import {
  Archive,
  Activity,
  GraduationCap,
  PlayCircle,
  PlusCircle,
  RefreshCw,
  Upload,
  Users,
} from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import type { SessionOut, StudentOut } from "@/lib/api/types";
import {
  formatDateTime,
  humanizeAction,
  useClasses,
  useRecentAudit,
} from "@/lib/lab";
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
  const sessionQs = useQueries({
    queries: (classList ?? []).map((c) => ({
      queryKey: ["class-sessions", c.id],
      queryFn: () => apiFetch<SessionOut[]>(`/api/classes/${c.id}/sessions`),
    })),
  });
  const studentQs = useQueries({
    queries: (classList ?? []).map((c) => ({
      queryKey: ["students", c.id],
      queryFn: () => apiFetch<StudentOut[]>(`/api/classes/${c.id}/students`),
    })),
  });
  const audit = useRecentAudit();

  const loadingClasses = classes.isPending;
  const sessionsReady = !!classList && sessionQs.every((q) => !q.isPending);
  const studentsReady = !!classList && studentQs.every((q) => !q.isPending);
  const sessions = sessionQs.flatMap((q) => q.data ?? []);
  const studentCount = studentQs.reduce((n, q) => n + (q.data?.length ?? 0), 0);
  const open = sessions.filter((s) => s.status === "active");
  const draft = sessions.filter((s) => s.status === "draft");
  const archived = sessions.filter((s) => s.status === "archived");
  const fetching =
    classes.isFetching ||
    audit.isFetching ||
    sessionQs.some((q) => q.isFetching) ||
    studentQs.some((q) => q.isFetching);

  function refresh() {
    qc.invalidateQueries({ queryKey: ["classes"] });
    qc.invalidateQueries({ queryKey: ["class-sessions"] });
    qc.invalidateQueries({ queryKey: ["students"] });
    qc.invalidateQueries({ queryKey: ["audit-recent"] });
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

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Classes"
          icon={GraduationCap}
          loading={loadingClasses}
          value={classList?.length ?? 0}
          hint="Classes you teach"
        />
        <StatCard
          label="Students"
          icon={Users}
          loading={loadingClasses || !studentsReady}
          value={studentCount}
          hint="Enrolled across your classes"
        />
        <StatCard
          label="Open sessions"
          icon={PlayCircle}
          loading={loadingClasses || !sessionsReady}
          value={open.length}
          hint={`${draft.length} draft`}
        />
        <StatCard
          label="Archived sessions"
          icon={Archive}
          loading={loadingClasses || !sessionsReady}
          value={archived.length}
          hint="Read-only history"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Panel
            title="Open sessions"
            action={
              <Link
                href="/instructor/classes"
                className="text-xs font-medium text-bank-accent hover:underline"
              >
                View classes
              </Link>
            }
          >
            {loadingClasses || !sessionsReady ? (
              <RowsSkeleton />
            ) : open.length ? (
              <ul className="divide-y divide-border">
                {open.map((s) => (
                  <li
                    key={s.id}
                    className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-text-strong">
                        {s.name}
                      </p>
                      <p className="truncate text-xs text-text-muted">
                        {s.class_name} · <span className="capitalize">{s.kind}</span>
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      <StatusBadge status={s.status} />
                      <Link href={`/instructor/sessions/${s.id}`}>
                        <Button size="sm" variant="outline">
                          Control
                        </Button>
                      </Link>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState
                className="rounded-none border-0"
                title="No open sessions"
                description="Open a session from one of your classes to start a lab."
              />
            )}
          </Panel>

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
                {classList.map((c, i) => (
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
                      <span className="text-xs text-text-muted tabular-nums">
                        {studentQs[i]?.data
                          ? `${studentQs[i].data.length} students`
                          : ""}
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

          <Panel title="Recent activity">
            {audit.isPending ? (
              <RowsSkeleton />
            ) : audit.isError ? (
              <div className="p-4">
                <ErrorMsg error={audit.error} />
              </div>
            ) : audit.data?.items.length ? (
              <ul className="divide-y divide-border">
                {audit.data.items.slice(0, 8).map((a) => (
                  <li key={a.id} className="flex gap-3 px-4 py-2.5">
                    <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-bank-sky-light text-bank-primary">
                      <Activity className="size-3.5" />
                    </span>
                    <div className="min-w-0 text-sm">
                      <p className="truncate font-medium text-text-strong">
                        {humanizeAction(a.action)}
                      </p>
                      <p className="truncate text-xs text-text-muted">
                        {a.actor_username ?? "system"} · {formatDateTime(a.at)}
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
      </div>
    </div>
  );
}
