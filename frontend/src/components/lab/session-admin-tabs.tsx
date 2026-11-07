"use client";

import { useMemo, useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { toast } from "sonner";
import {
  Activity,
  Check,
  Lock,
  Play,
  RotateCcw,
  Search,
  X,
} from "lucide-react";
import type {
  BusinessDayOut,
  PermissionCell,
  SessionOut,
} from "@/lib/api/types";
import {
  BANK_ROLES,
  ROLE_LABEL,
  SESSION_ACTION_OPTIONS,
  actionCategory,
  actionLabel,
  dayLabel,
  formatDateTime,
  relativeTime,
  useAudit,
  useBusinessDays,
  useClearOverride,
  usePermissionMatrix,
  useSessionTransition,
  useSetOverride,
} from "@/lib/lab";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { Avatar } from "@/components/shared/avatar";
import { DataTable } from "@/components/shared/data-table";
import { EmptyState } from "@/components/shared/empty-state";
import { Pagination } from "@/components/shared/pagination";
import { StatusBadge } from "@/components/shared/status-badge";
import { ConfirmButton, ErrorMsg, Labeled, QueryState, TextInput } from "./common";
import { formatTemplateLabel } from "./common";
import { cn } from "@/lib/utils";

// ---------------- Permissions ----------------
function Cell({
  cell,
  sessionId,
  readOnly,
}: {
  cell: PermissionCell;
  sessionId: string;
  readOnly: boolean;
}) {
  const set = useSetOverride(sessionId);
  const clear = useClearOverride(sessionId);
  const allowed = !!cell.effective_scope;
  const overridden = cell.override !== null && cell.override !== undefined;
  const roleName = ROLE_LABEL[cell.role] ?? cell.role;
  const scope = cell.effective_scope === "own" ? "Own" : "All";
  const err = (set.error ?? clear.error) as Error | null;

  function toggle() {
    set.mutate(
      {
        role: cell.role,
        permission_code: cell.permission_code,
        allowed: !allowed,
      },
      {
        onSuccess: () =>
          toast.success(
            `${roleName}: ${cell.permission_code} ${!allowed ? "allowed" : "denied"} for this session`,
          ),
        onError: (e) => toast.error(e.message),
      },
    );
  }

  const pill = (
    <>
      {allowed ? <Check className="size-3.5" /> : <X className="size-3.5" />}
      {allowed ? scope : "No"}
    </>
  );
  const pillCls = cn(
    "inline-flex h-7 min-w-16 items-center justify-center gap-1 rounded-full px-2.5 text-xs font-medium transition-colors",
    allowed
      ? "bg-fin-success-bg text-fin-success-dark"
      : "bg-hover text-text-muted",
    overridden && "ring-2 ring-bank-accent ring-offset-1",
  );

  return (
    <td className="border-b border-border px-2 py-2 text-center align-middle">
      <div className="flex flex-col items-center gap-1">
        {readOnly ? (
          <span className={pillCls}>{pill}</span>
        ) : (
          <button
            type="button"
            disabled={set.isPending}
            onClick={toggle}
            aria-label={`${roleName}: ${cell.permission_code} is ${allowed ? `allowed (${scope})` : "denied"}. Click to ${allowed ? "deny" : "allow"}.`}
            className={cn(pillCls, "cursor-pointer hover:brightness-95 disabled:opacity-50")}
          >
            {pill}
          </button>
        )}
        {overridden && (
          <span className="flex items-center gap-1">
            <span className="rounded bg-bank-sky-light px-1.5 text-[10px] font-semibold tracking-wide text-bank-primary uppercase">
              Override
            </span>
            {!readOnly && (
              <button
                type="button"
                disabled={clear.isPending}
                onClick={() =>
                  clear.mutate(
                    { role: cell.role, permission_code: cell.permission_code },
                    {
                      onSuccess: () =>
                        toast.success(`${roleName}: reset to default`),
                      onError: (e) => toast.error(e.message),
                    },
                  )
                }
                className="inline-flex items-center gap-0.5 text-[11px] text-text-muted hover:text-text-strong disabled:opacity-50"
              >
                <RotateCcw className="size-3" /> Reset
              </button>
            )}
          </span>
        )}
        {err && <span className="text-[11px] text-fin-danger">{err.message}</span>}
      </div>
    </td>
  );
}

function Legend() {
  return (
    <ul className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-text-muted">
      <li className="flex items-center gap-1.5">
        <span className="inline-flex h-5 items-center gap-1 rounded-full bg-fin-success-bg px-2 font-medium text-fin-success-dark">
          <Check className="size-3" /> All
        </span>
        Allowed for the whole bank
      </li>
      <li className="flex items-center gap-1.5">
        <span className="inline-flex h-5 items-center gap-1 rounded-full bg-fin-success-bg px-2 font-medium text-fin-success-dark">
          <Check className="size-3" /> Own
        </span>
        Allowed for own work only
      </li>
      <li className="flex items-center gap-1.5">
        <span className="inline-flex h-5 items-center gap-1 rounded-full bg-hover px-2 font-medium text-text-muted">
          <X className="size-3" /> No
        </span>
        Not allowed
      </li>
      <li className="flex items-center gap-1.5">
        <span className="inline-flex h-5 items-center rounded-full bg-hover px-2 font-medium text-text-muted ring-2 ring-bank-accent">
          &nbsp;
        </span>
        <span className="rounded bg-bank-sky-light px-1.5 text-[10px] font-semibold tracking-wide text-bank-primary uppercase">
          Override
        </span>
        Changed for this session
      </li>
    </ul>
  );
}

export function PermissionsTab({
  session,
  readOnly,
}: {
  session: SessionOut;
  readOnly: boolean;
}) {
  const matrix = usePermissionMatrix(session.id);
  const [q, setQ] = useState("");
  const cells = useMemo(() => matrix.data ?? [], [matrix.data]);
  const { codes, byKey, meta, categories } = useMemo(() => {
    const term = q.trim().toLowerCase();
    const meta = new Map(cells.map((c) => [c.permission_code, c]));
    const codes = Array.from(meta.keys()).filter(
      (code) =>
        !term ||
        code.toLowerCase().includes(term) ||
        (meta.get(code)?.description ?? "").toLowerCase().includes(term),
    );
    return {
      codes,
      meta,
      byKey: new Map(cells.map((c) => [`${c.permission_code}|${c.role}`, c])),
      categories: Array.from(new Set(cells.map((c) => c.category))),
    };
  }, [cells, q]);

  return (
    <QueryState query={matrix}>
      {cells.length === 0 ? (
        <EmptyState title="No permissions found" />
      ) : (
        <div className="space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <p className="max-w-xl text-sm text-text-muted">
              Defaults come from the role matrix. Click a cell to override a role
              for this session only. Separation-of-duties rules cannot be
              overridden and the server rejects them.
            </p>
            <div className="relative w-full sm:w-64">
              <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-text-muted" />
              <Input
                aria-label="Search permissions"
                placeholder="Search permissions…"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                className="pl-8"
              />
            </div>
          </div>
          <Legend />
          {readOnly && (
            <p className="flex items-center gap-2 text-sm text-text-muted">
              <Lock className="size-4" /> Read-only while the session is archived.
            </p>
          )}
          <div className="max-h-[70vh] overflow-auto rounded-xl border border-border bg-card shadow-xs">
            <table className="w-full min-w-max border-separate border-spacing-0 text-left text-sm text-text-body">
              <thead>
                <tr>
                  <th className="sticky top-0 left-0 z-30 min-w-64 border-b border-border bg-surface px-4 py-3 text-xs font-medium tracking-wide text-text-muted uppercase">
                    Permission
                  </th>
                  {BANK_ROLES.map((r) => (
                    <th
                      key={r}
                      className="sticky top-0 z-20 border-b border-border bg-surface px-3 py-3 text-center text-xs font-medium tracking-wide whitespace-nowrap text-text-muted uppercase"
                    >
                      {ROLE_LABEL[r]}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {categories.map((cat) => {
                  const rows = codes.filter((c) => meta.get(c)?.category === cat);
                  if (!rows.length) return null;
                  return (
                    <CategoryRows
                      key={cat}
                      category={cat}
                      codes={rows}
                      meta={meta}
                      byKey={byKey}
                      sessionId={session.id}
                      readOnly={readOnly}
                    />
                  );
                })}
                {codes.length === 0 && (
                  <tr>
                    <td colSpan={BANK_ROLES.length + 1}>
                      <EmptyState
                        className="rounded-none border-0"
                        title="No matching permissions"
                        description="Try a different search term."
                      />
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </QueryState>
  );
}

function CategoryRows({
  category,
  codes,
  meta,
  byKey,
  sessionId,
  readOnly,
}: {
  category: string;
  codes: string[];
  meta: Map<string, PermissionCell>;
  byKey: Map<string, PermissionCell>;
  sessionId: string;
  readOnly: boolean;
}) {
  return (
    <>
      <tr>
        <th
          scope="colgroup"
          colSpan={BANK_ROLES.length + 1}
          className="sticky left-0 border-b border-border bg-hover px-4 py-1.5 text-left text-xs font-semibold tracking-wide text-text-strong uppercase"
        >
          {category}
        </th>
      </tr>
      {codes.map((code) => (
        <tr key={code} className="group">
          <th
            scope="row"
            className="sticky left-0 z-10 border-b border-border bg-card px-4 py-2 text-left font-normal group-hover:bg-hover"
          >
            <div className="font-mono text-xs font-medium text-text-strong">
              {code}
            </div>
            <div className="max-w-64 text-xs whitespace-normal text-text-muted">
              {meta.get(code)?.description}
            </div>
          </th>
          {BANK_ROLES.map((r) => {
            const cell = byKey.get(`${code}|${r}`);
            return cell ? (
              <Cell key={r} cell={cell} sessionId={sessionId} readOnly={readOnly} />
            ) : (
              <td
                key={r}
                className="border-b border-border text-center text-text-muted"
              >
                —
              </td>
            );
          })}
        </tr>
      ))}
    </>
  );
}

// ---------------- Activity ----------------
const PAGE_SIZE = 25;

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
            className="h-8 pl-8"
          />
        </div>
        <Select
          aria-label="Filter by action"
          value={action}
          onChange={(e) => {
            setAction(e.target.value);
            setPage(1);
          }}
          className="h-8 w-52"
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
          className="h-8 w-44"
        >
          <option value="">All actors</option>
          {actors.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </Select>
        {(action || actor || q) && (
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

      <QueryState query={audit}>
        {groups.length === 0 ? (
          <EmptyState
            icon={Activity}
            title="No activity found"
            description={
              action || actor || q
                ? "No entries match these filters."
                : "Actions taken in this session will appear here."
            }
          />
        ) : (
          <div className="space-y-5">
            {groups.map(([day, rows]) => (
              <section key={day}>
                <h3 className="mb-2 text-xs font-semibold tracking-wide text-text-muted uppercase">
                  {day}
                </h3>
                <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-card shadow-xs">
                  {rows.map((a) => (
                    <li
                      key={a.id}
                      className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 hover:bg-hover"
                    >
                      <Avatar name={a.actor_username ?? "System"} />
                      <div className="min-w-0 flex-1">
                        <p className="flex flex-wrap items-center gap-2 text-sm">
                          <span className="font-medium text-text-strong">
                            {actionLabel(a.action)}
                          </span>
                          <StatusBadge
                            status={a.action}
                            tone="info"
                            label={actionCategory(a.action)}
                          />
                          <span className="rounded-md border border-border bg-surface px-1.5 text-xs text-text-body">
                            {a.entity_type}
                          </span>
                        </p>
                        <p className="mt-0.5 truncate text-xs text-text-muted">
                          {a.actor_username ?? "system"}{" "}
                          <span>({a.actor_role})</span>
                          {" · "}
                          <span className="font-mono">{a.action}</span>
                        </p>
                      </div>
                      <time
                        dateTime={a.at}
                        title={formatDateTime(a.at)}
                        className="text-xs whitespace-nowrap text-text-muted"
                      >
                        {relativeTime(a.at)}
                      </time>
                    </li>
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


// ---------------- Settings ----------------
function Section({
  title,
  description,
  action,
  children,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="overflow-hidden rounded-xl border border-border bg-card shadow-xs">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-5 py-4">
        <div>
          <h2 className="text-sm font-semibold text-text-strong">{title}</h2>
          {description && (
            <p className="mt-0.5 text-sm text-text-muted">{description}</p>
          )}
        </div>
        {action && <div className="flex items-center gap-2">{action}</div>}
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

export function SettingsTab({ session }: { session: SessionOut }) {
  const t = useSessionTransition(session.id);
  const days = useBusinessDays(session.id);
  const [groups, setGroups] = useState("2");
  const [groupErr, setGroupErr] = useState<string | null>(null);
  const perGroup = session.structure === "per_group";
  const ok = (m: string) => ({
    onSuccess: () => toast.success(m),
    onError: (e: Error) => toast.error(e.message),
  });

  function open() {
    if (perGroup) {
      const n = Number(groups);
      if (!Number.isInteger(n) || n < 1) {
        setGroupErr("Enter a whole number of groups (1 or more)");
        return;
      }
      setGroupErr(null);
      t.mutate({ action: "open", group_count: n }, ok("Session opened"));
    } else {
      t.mutate({ action: "open" }, ok("Session opened"));
    }
  }

  const dayColumns: ColumnDef<BusinessDayOut>[] = [
    {
      accessorKey: "bank_name",
      header: "Bank",
      cell: ({ getValue }) => (
        <span className="font-medium text-text-strong">{getValue<string>()}</span>
      ),
    },
    {
      accessorKey: "date",
      header: "Business date",
      cell: ({ getValue }) => (
        <span className="tabular-nums">{getValue<string>()}</span>
      ),
    },
    {
      accessorKey: "status",
      header: "Day status",
      cell: ({ getValue }) => <StatusBadge status={getValue<string>()} />,
    },
  ];

  const dl: [string, React.ReactNode][] = [
    ["Kind", <span key="k" className="capitalize">{session.kind}</span>],
    ["Structure", perGroup ? "One bank per group" : formatTemplateLabel(session.structure)],
    ["Opened", formatDateTime(session.opened_at)],
    ["Archived", formatDateTime(session.archived_at)],
  ];

  return (
    <div className="space-y-6">
      <Section
        title="Session status"
        description={
          session.status === "draft"
            ? "The session is a draft. Open it when members are ready."
            : session.status === "active"
              ? "The session is open for students."
              : "The session is archived and read-only."
        }
        action={<StatusBadge status={session.status} className="h-6 px-2.5 text-sm" />}
      >
        <dl className="grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
          {dl.map(([k, v]) => (
            <div key={k}>
              <dt className="text-xs font-medium tracking-wide text-text-muted uppercase">
                {k}
              </dt>
              <dd className="mt-1 font-medium text-text-strong">{v}</dd>
            </div>
          ))}
        </dl>
        <div className="mt-5 flex flex-wrap items-end justify-between gap-4 border-t border-border pt-4">
          <div className="min-w-0 flex-1">
            {session.status === "draft" && perGroup && (
              <div className="max-w-40">
                <Labeled label="Number of groups" error={groupErr ?? undefined}>
                  <TextInput
                    type="number"
                    min={1}
                    value={groups}
                    onChange={(e) => setGroups(e.target.value)}
                  />
                </Labeled>
              </div>
            )}
            <ErrorMsg error={t.error} />
          </div>
          <div className="flex gap-2">
            {session.status === "draft" && (
              <Button disabled={t.isPending} onClick={open}>
                <Play /> {t.isPending ? "Opening…" : "Open session"}
              </Button>
            )}
            {session.status === "active" && (
              <ConfirmButton
                label="Archive session"
                message="Archive this session? It becomes read-only for everyone."
                variant="destructive"
                size="default"
                pending={t.isPending}
                onConfirm={() => t.mutate({ action: "archive" }, ok("Session archived"))}
              />
            )}
            {session.status === "archived" && (
              <ConfirmButton
                label="Re-open session"
                message="Re-open this archived session?"
                size="default"
                pending={t.isPending}
                onConfirm={() => t.mutate({ action: "reopen" }, ok("Session re-opened"))}
              />
            )}
          </div>
        </div>
      </Section>

      <Section
        title="Business date per bank"
        description="Each bank keeps its own business date once the session is open."
      >
        <DataTable
          columns={dayColumns}
          data={days.data}
          isLoading={days.isPending}
          error={days.error}
          getRowId={(d) => d.bank_id}
          columnToggle={false}
          searchPlaceholder="Search banks…"
          emptyTitle="No business days yet"
          emptyDescription="Business days appear once the session is open."
        />
      </Section>
    </div>
  );
}
