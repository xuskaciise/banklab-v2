"use client";

import { toast } from "sonner";
import { RotateCcw } from "lucide-react";
import type { PermissionCell } from "@/lib/api/types";
import {
  BANK_ROLES,
  ROLE_LABEL,
  useClearOverride,
  useSetOverride,
} from "@/lib/lab";
import { cn } from "@/lib/utils";

const FOCUS =
  "outline-none focus-visible:ring-2 focus-visible:ring-bank-accent focus-visible:ring-offset-2";

const CATEGORY_LABEL: Record<string, string> = {
  account: "Accounts",
  approval: "Approvals",
  audit: "Audit",
  cash: "Cash movements",
  cheque: "Cheques",
  chequebook: "Cheques",
  customer: "Customers",
  eod: "End of day",
  gl: "General ledger",
  report: "Reports",
  till: "Tills",
  txn: "Transactions",
  vault: "Vault",
};

export const categoryLabel = (c: string) =>
  CATEGORY_LABEL[c.toLowerCase()] ?? c.charAt(0).toUpperCase() + c.slice(1);

/** Role picker: one tab per role with how many permissions it has. */
export function RoleTabs({
  cells,
  role,
  onChange,
}: {
  cells: PermissionCell[];
  role: string;
  onChange: (r: string) => void;
}) {
  return (
    <div role="tablist" aria-label="Role" className="flex flex-wrap gap-2">
      {BANK_ROLES.map((r) => {
        const on = r === role;
        const n = cells.filter((c) => c.role === r && c.effective_scope).length;
        return (
          <button
            key={r}
            type="button"
            role="tab"
            aria-selected={on}
            onClick={() => onChange(r)}
            className={cn(
              "flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition-colors",
              FOCUS,
              on
                ? "border-bank-primary bg-bank-sky-light text-bank-primary"
                : "border-border bg-card text-text-body hover:bg-hover",
            )}
          >
            {ROLE_LABEL[r]}
            <span
              className={cn(
                "rounded-full px-1.5 text-xs tabular-nums",
                on ? "bg-bank-primary text-white" : "bg-hover text-text-muted",
              )}
            >
              {n}
            </span>
          </button>
        );
      })}
    </div>
  );
}

function PermissionRow({
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
  const title = cell.description || cell.permission_code;
  const busy = set.isPending || clear.isPending;
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
            `${roleName}: "${title}" ${!allowed ? "allowed" : "turned off"} for this session`,
          ),
        onError: (e) => toast.error(e.message),
      },
    );
  }

  return (
    <li className="flex items-center justify-between gap-4 px-4 py-3">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium text-text-strong">{title}</span>
          {allowed && (
            <span className="rounded-full bg-fin-success-bg px-2 text-xs font-medium text-fin-success-dark">
              {cell.effective_scope === "own" ? "Own work only" : "Whole bank"}
            </span>
          )}
          {overridden && (
            <span className="rounded bg-bank-sky-light px-1.5 text-[10px] font-semibold tracking-wide text-bank-primary uppercase">
              Changed for this session
            </span>
          )}
        </div>
        <p className="font-mono text-xs text-text-muted">
          {cell.permission_code}
        </p>
        {err && <p className="text-xs text-fin-danger">{err.message}</p>}
      </div>
      <div className="flex shrink-0 items-center gap-3">
        {overridden && !readOnly && (
          <button
            type="button"
            disabled={busy}
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
            className={cn(
              "inline-flex items-center gap-1 rounded text-xs text-text-muted hover:text-text-strong disabled:opacity-50",
              FOCUS,
            )}
          >
            <RotateCcw className="size-3" aria-hidden /> Reset
          </button>
        )}
        <button
          type="button"
          role="switch"
          aria-checked={allowed}
          aria-label={`${roleName}: ${title}`}
          disabled={readOnly || busy}
          onClick={toggle}
          className={cn(
            "relative inline-flex h-6 w-11 items-center rounded-full transition-colors disabled:cursor-not-allowed disabled:opacity-50",
            FOCUS,
            allowed ? "bg-bank-primary" : "bg-border",
          )}
        >
          <span
            aria-hidden
            className={cn(
              "inline-block size-5 rounded-full bg-card shadow-xs transition-transform",
              allowed ? "translate-x-5.5" : "translate-x-0.5",
            )}
          />
        </button>
      </div>
    </li>
  );
}

/** One role's permissions, grouped in cards by category. */
export function RolePermissions({
  cells,
  role,
  codes,
  categories,
  sessionId,
  readOnly,
}: {
  cells: PermissionCell[];
  role: string;
  codes: string[];
  categories: string[];
  sessionId: string;
  readOnly: boolean;
}) {
  const mine = cells.filter(
    (c) => c.role === role && codes.includes(c.permission_code),
  );
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {categories.map((cat) => {
        const rows = mine.filter((c) => c.category === cat);
        if (!rows.length) return null;
        const on = rows.filter((c) => c.effective_scope).length;
        return (
          <section
            key={cat}
            className="overflow-hidden rounded-xl border border-border bg-card shadow-xs"
          >
            <header className="flex items-center justify-between border-b border-border bg-surface px-4 py-2.5">
              <h3 className="text-sm font-semibold text-text-strong">
                {categoryLabel(cat)}
              </h3>
              <span className="text-xs text-text-muted tabular-nums">
                {on} of {rows.length} allowed
              </span>
            </header>
            <ul className="divide-y divide-border">
              {rows.map((c) => (
                <PermissionRow
                  key={c.permission_code}
                  cell={c}
                  sessionId={sessionId}
                  readOnly={readOnly}
                />
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
