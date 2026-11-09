"use client";

import { useMemo, useState } from "react";
import {
  Activity,
  Building2,
  PlayCircle,
  Search,
  ShieldCheck,
  UserCog,
  Users,
} from "lucide-react";
import type { AuditOut } from "@/lib/api/types";
import {
  SESSION_ACTION_OPTIONS,
  actionCategory,
  actionLabel,
  dayLabel,
  formatDateTime,
  relativeTime,
  roleLabel,
  useAudit,
} from "@/lib/lab";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { EmptyState } from "@/components/shared/empty-state";
import { Pagination } from "@/components/shared/pagination";
import { QueryState } from "./common";

const PAGE_SIZE = 25;

type Meta = { icon: React.ComponentType<{ className?: string }>; tint: string };
const CATEGORY: Record<string, Meta> = {
  Session: { icon: PlayCircle, tint: "bg-fin-success-bg text-fin-success-dark" },
  Banks: { icon: Building2, tint: "bg-bank-sky-light text-bank-primary" },
  Members: { icon: Users, tint: "bg-bank-sky-light text-bank-accent" },
  Permissions: { icon: ShieldCheck, tint: "bg-fin-pending-bg text-fin-pending" },
  Roles: { icon: UserCog, tint: "bg-hover text-text-body" },
};
const metaOf = (cat: string): Meta =>
  CATEGORY[cat] ?? { icon: Activity, tint: "bg-hover text-text-muted" };

const scalar = (v: unknown): v is string | number | boolean =>
  ["string", "number", "boolean"].includes(typeof v);
const asObj = (v: unknown): Record<string, unknown> =>
  v && typeof v === "object" && !Array.isArray(v)
    ? (v as Record<string, unknown>)
    : {};

/** Short readable detail built only from fields present in before/after. */
function detailLine(a: AuditOut): string | null {
  const before = asObj(a.before);
  const after = asObj(a.after);
  const parts: string[] = [];
  for (const [k, v] of Object.entries(after)) {
    if (!scalar(v) || k === "id" || k.endsWith("_id")) continue;
    const label = k.replace(/_/g, " ");
    const b = before[k];
    parts.push(
      scalar(b) && b !== v ? `${label}: ${b} → ${v}` : `${label}: ${v}`,
    );
    if (parts.length === 3) break;
  }
  return parts.length ? parts.join(" · ") : null;
}

function Entry({ a }: { a: AuditOut }) {
  const cat = actionCategory(a.action);
  const { icon: Icon, tint } = metaOf(cat);
  const detail = detailLine(a);
  return (
    <li className="relative pl-12">
      <span
        className={cn(
          "absolute top-0.5 left-0 flex size-8 items-center justify-center rounded-full ring-4 ring-surface",
          tint,
        )}
      >
        <Icon className="size-4" aria-hidden />
      </span>
      <div className="rounded-lg border border-border bg-card px-4 py-3 shadow-xs">
        <div className="flex items-start justify-between gap-3">
          <p className="min-w-0 text-sm">
            <span className="font-semibold text-text-strong">
              {a.actor_username ?? "System"}
            </span>
            <span className="text-text-muted"> · </span>
            <span className="text-text-body">{actionLabel(a.action)}</span>
          </p>
          <time
            dateTime={a.at}
            title={formatDateTime(a.at)}
            className="text-xs whitespace-nowrap text-text-muted"
          >
            {relativeTime(a.at)}
          </time>
        </div>
        {detail && <p className="mt-1 text-sm text-text-body">{detail}</p>}
        <details className="group mt-1.5 text-xs text-text-muted">
          <summary className="cursor-pointer rounded outline-none select-none hover:text-text-strong focus-visible:ring-2 focus-visible:ring-bank-accent">
            Details
          </summary>
          <dl className="mt-1.5 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
            <dt>Action</dt>
            <dd className="font-mono">{a.action}</dd>
            <dt>Subject</dt>
            <dd className="font-mono break-all">
              {a.entity_type} {a.entity_id}
            </dd>
            <dt>Role</dt>
            <dd>{roleLabel(a.actor_role)}</dd>
            <dt>Time</dt>
            <dd>{formatDateTime(a.at)}</dd>
          </dl>
        </details>
      </div>
    </li>
  );
}

export function ActivityTab({ sessionId }: { sessionId: string }) {
  const [page, setPage] = useState(1);
  const [action, setAction] = useState("");
  const [actor, setActor] = useState("");
  const [q, setQ] = useState("");
  const audit = useAudit(sessionId, page, action);
  const items = useMemo(() => audit.data?.items ?? [], [audit.data]);
  const actors = useMemo(
    () =>
      Array.from(
        new Set(items.map((a) => a.actor_username).filter(Boolean) as string[]),
      ).sort(),
    [items],
  );
  const term = q.trim().toLowerCase();
  const shown = items.filter(
    (a) =>
      (!actor || a.actor_username === actor) &&
      (!term ||
        `${actionLabel(a.action)} ${a.action} ${a.actor_username ?? ""} ${a.entity_type}`
          .toLowerCase()
          .includes(term)),
  );
  const groups = useMemo(() => {
    const m = new Map<string, typeof shown>();
    for (const a of shown) {
      const k = dayLabel(a.at);
      m.set(k, [...(m.get(k) ?? []), a]);
    }
    return Array.from(m.entries());
  }, [shown]);
  const counts = useMemo(() => {
    const m = new Map<string, number>();
    for (const a of shown) {
      const c = actionCategory(a.action);
      m.set(c, (m.get(c) ?? 0) + 1);
    }
    return Array.from(m.entries());
  }, [shown]);
  const filtered = !!(action || actor || q);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card px-3 py-2.5 shadow-xs">
        <div className="relative min-w-0 flex-1 sm:max-w-xs">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-text-muted" />
          <Input
            aria-label="Search activity"
            placeholder="Search this page…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="h-8 pl-8 text-sm"
          />
        </div>
        <Select
          aria-label="Filter by action"
          value={action}
          onChange={(e) => {
            setAction(e.target.value);
            setPage(1);
          }}
          className="h-8 w-52 text-sm"
        >
          <option value="">All actions</option>
          {SESSION_ACTION_OPTIONS.map((o) => (
            <option key={o.code} value={o.code}>
              {o.category}: {o.label}
            </option>
          ))}
        </Select>
        <Select
          aria-label="Filter by actor"
          value={actor}
          onChange={(e) => setActor(e.target.value)}
          className="h-8 w-44 text-sm"
        >
          <option value="">All actors</option>
          {actors.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </Select>
        {filtered && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setAction("");
              setActor("");
              setQ("");
              setPage(1);
            }}
          >
            Reset filters
          </Button>
        )}
      </div>

      {counts.length > 0 && (
        <ul className="flex flex-wrap gap-2" aria-label="Entries on this page">
          {counts.map(([c, n]) => {
            const { icon: Icon, tint } = metaOf(c);
            return (
              <li
                key={c}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
                  tint,
                )}
              >
                <Icon className="size-3" aria-hidden />
                {c}
                <span className="tabular-nums">{n}</span>
              </li>
            );
          })}
        </ul>
      )}

      <QueryState query={audit}>
        {groups.length === 0 ? (
          <EmptyState
            icon={Activity}
            title={filtered ? "No matching activity" : "No activity yet"}
            description={
              filtered
                ? "No entries match these filters. Try resetting them."
                : "Opening the session, adding members and changing roles will show up here as a timeline."
            }
          />
        ) : (
          <div className="space-y-6">
            {groups.map(([day, rows]) => (
              <section key={day}>
                <h3 className="mb-3 text-xs font-semibold tracking-wide text-text-muted uppercase">
                  {day}
                </h3>
                <ul className="relative space-y-3 before:absolute before:top-2 before:bottom-2 before:left-4 before:w-px before:bg-border">
                  {rows.map((a) => (
                    <Entry key={a.id} a={a} />
                  ))}
                </ul>
              </section>
            ))}
          </div>
        )}
        <Pagination
          page={page}
          pageSize={PAGE_SIZE}
          total={audit.data?.count ?? 0}
          onPageChange={setPage}
        />
      </QueryState>
    </div>
  );
}
