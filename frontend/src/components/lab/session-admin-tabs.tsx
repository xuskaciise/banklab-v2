"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";
import { Check, Lock, RotateCcw, Search, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import type { PermissionCell, SessionOut } from "@/lib/api/types";
import {
  BANK_ROLES,
  ROLE_LABEL,
  useClearOverride,
  usePermissionMatrix,
  useSetOverride,
} from "@/lib/lab";
import { EmptyState } from "@/components/shared/empty-state";
import { QueryState } from "./common";
import { cn } from "@/lib/utils";
import {
  RolePermissions,
  RoleTabs,
  categoryLabel,
} from "./permissions-by-role";

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
            className={cn(
              pillCls,
              "cursor-pointer hover:brightness-95 disabled:opacity-50",
            )}
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
        {err && (
          <span className="text-[11px] text-fin-danger">{err.message}</span>
        )}
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
  const [view, setView] = useState<"role" | "matrix">("role");
  const [role, setRole] = useState<string>(BANK_ROLES[0]);
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
              Choose a role to see what it may do. Turning a switch changes it
              for this session only. Separation-of-duties rules cannot be
              changed and the server rejects them.
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
          <div className="flex flex-wrap items-center justify-between gap-3">
            {view === "role" ? (
              <RoleTabs cells={cells} role={role} onChange={setRole} />
            ) : (
              <Legend />
            )}
            <div className="inline-flex rounded-lg border border-border bg-card p-0.5 text-sm">
              {(["role", "matrix"] as const).map((v) => (
                <button
                  key={v}
                  type="button"
                  aria-pressed={view === v}
                  onClick={() => setView(v)}
                  className={cn(
                    "rounded-md px-3 py-1.5 font-medium outline-none focus-visible:ring-2 focus-visible:ring-bank-accent",
                    view === v
                      ? "bg-bank-sky-light text-bank-primary"
                      : "text-text-muted hover:text-text-strong",
                  )}
                >
                  {v === "role" ? "By role" : "Compare roles"}
                </button>
              ))}
            </div>
          </div>
          {readOnly && (
            <p className="flex items-center gap-2 text-sm text-text-muted">
              <Lock className="size-4" /> Read-only while the session is
              archived.
            </p>
          )}
          {view === "role" ? (
            codes.length ? (
              <RolePermissions
                cells={cells}
                role={role}
                codes={codes}
                categories={categories}
                sessionId={session.id}
                readOnly={readOnly}
              />
            ) : (
              <EmptyState
                title="No matching permissions"
                description="Try a different search term."
              />
            )
          ) : (
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
                    const rows = codes.filter(
                      (c) => meta.get(c)?.category === cat,
                    );
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
          )}
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
          {categoryLabel(category)}
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
              <Cell
                key={r}
                cell={cell}
                sessionId={sessionId}
                readOnly={readOnly}
              />
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

export { ActivityTab } from "./activity-tab";
export { SettingsTab } from "./settings-tab";
