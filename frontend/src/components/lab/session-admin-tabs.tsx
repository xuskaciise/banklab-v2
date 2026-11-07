"use client";

import { useState } from "react";
import { toast } from "sonner";
import type { PermissionCell, SessionOut } from "@/lib/api/types";
import {
  BANK_ROLES,
  ROLE_LABEL,
  formatDateTime,
  useAudit,
  useBusinessDays,
  useClearOverride,
  usePermissionMatrix,
  useSessionTransition,
  useSetOverride,
} from "@/lib/lab";
import { Button } from "@/components/ui/button";
import {
  ConfirmButton,
  Empty,
  ErrorMsg,
  Labeled,
  QueryState,
  StatusBadge,
  Table,
  Td,
  TextInput,
  Th,
} from "./common";
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
  return (
    <td className="border-b border-border px-2 py-1.5 text-center align-middle">
      <div className="flex flex-col items-center gap-1">
        <span
          className={cn(
            "text-xs font-medium",
            allowed ? "text-fin-success-dark" : "text-text-muted",
          )}
        >
          {allowed ? `Yes (${cell.effective_scope})` : "No"}
        </span>
        {overridden && (
          <span className="rounded bg-fin-pending-bg px-1.5 text-[10px] font-medium text-fin-pending">
            Override
          </span>
        )}
        {!readOnly && (
          <div className="flex gap-1">
            <button
              type="button"
              disabled={set.isPending}
              onClick={() =>
                set.mutate({
                  role: cell.role,
                  permission_code: cell.permission_code,
                  allowed: !allowed,
                })
              }
              className="text-[11px] text-bank-accent hover:underline disabled:opacity-50"
            >
              {allowed ? "Deny" : "Allow"}
            </button>
            {overridden && (
              <button
                type="button"
                disabled={clear.isPending}
                onClick={() =>
                  clear.mutate({
                    role: cell.role,
                    permission_code: cell.permission_code,
                  })
                }
                className="text-[11px] text-text-muted hover:underline disabled:opacity-50"
              >
                Clear
              </button>
            )}
          </div>
        )}
        {(set.error || clear.error) && (
          <span className="text-[11px] text-fin-danger">
            {((set.error ?? clear.error) as Error).message}
          </span>
        )}
      </div>
    </td>
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
  const cells = matrix.data ?? [];
  const codes = Array.from(new Set(cells.map((c) => c.permission_code)));
  const byKey = new Map(cells.map((c) => [`${c.permission_code}|${c.role}`, c]));
  const meta = new Map(cells.map((c) => [c.permission_code, c]));
  const categories = Array.from(new Set(cells.map((c) => c.category)));
  return (
    <QueryState query={matrix}>
      {codes.length === 0 ? (
        <Empty>No permissions found.</Empty>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-text-muted">
            Defaults come from the role matrix. Override a role for this session
            only; separation-of-duties rules cannot be overridden and the server
            rejects them.
          </p>
          <Table>
            <thead>
              <tr>
                <Th>Permission</Th>
                {BANK_ROLES.map((r) => (
                  <Th key={r} className="text-center">
                    {ROLE_LABEL[r]}
                  </Th>
                ))}
              </tr>
            </thead>
            <tbody>
              {categories.map((cat) => (
                <CategoryRows
                  key={cat}
                  category={cat}
                  codes={codes.filter((c) => meta.get(c)?.category === cat)}
                  meta={meta}
                  byKey={byKey}
                  sessionId={session.id}
                  readOnly={readOnly}
                />
              ))}
            </tbody>
          </Table>
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
        <td
          colSpan={BANK_ROLES.length + 1}
          className="bg-hover px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-text-muted"
        >
          {category}
        </td>
      </tr>
      {codes.map((code) => (
        <tr key={code}>
          <Td>
            <div className="font-mono text-xs text-text-strong">{code}</div>
            <div className="text-xs text-text-muted">
              {meta.get(code)?.description}
            </div>
          </Td>
          {BANK_ROLES.map((r) => {
            const cell = byKey.get(`${code}|${r}`);
            return cell ? (
              <Cell key={r} cell={cell} sessionId={sessionId} readOnly={readOnly} />
            ) : (
              <Td key={r} className="text-center text-text-muted">
                —
              </Td>
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
  const [filter, setFilter] = useState("");
  const [applied, setApplied] = useState("");
  const audit = useAudit(sessionId, page, applied);
  const pages = Math.max(1, Math.ceil((audit.data?.count ?? 0) / PAGE_SIZE));
  return (
    <div className="space-y-3">
      <form
        className="flex max-w-md items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setPage(1);
          setApplied(filter.trim());
        }}
      >
        <Labeled label="Filter by action">
          <TextInput
            placeholder="e.g. lab.session_opened"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </Labeled>
        <Button type="submit" variant="outline">
          Filter
        </Button>
      </form>
      <QueryState query={audit}>
        {audit.data?.items.length ? (
          <>
            <Table>
              <thead>
                <tr>
                  <Th>When</Th>
                  <Th>Actor</Th>
                  <Th>Action</Th>
                  <Th>Entity</Th>
                </tr>
              </thead>
              <tbody>
                {audit.data.items.map((a) => (
                  <tr key={a.id} className="hover:bg-hover">
                    <Td className="whitespace-nowrap text-text-muted">
                      {formatDateTime(a.at)}
                    </Td>
                    <Td>
                      {a.actor_username ?? "system"}{" "}
                      <span className="text-xs text-text-muted">
                        ({a.actor_role})
                      </span>
                    </Td>
                    <Td className="font-mono text-xs">{a.action}</Td>
                    <Td className="text-text-muted">{a.entity_type}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
            <div className="flex items-center gap-3 text-sm text-text-muted">
              <Button
                size="sm"
                variant="outline"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </Button>
              Page {page} of {pages}
              <Button
                size="sm"
                variant="outline"
                disabled={page >= pages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </>
        ) : (
          <Empty>No activity recorded for this session.</Empty>
        )}
      </QueryState>
    </div>
  );
}

// ---------------- Settings ----------------
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

  return (
    <div className="space-y-6">
      <section className="space-y-3 rounded-xl border border-border bg-card p-5 shadow-xs">
        <div className="flex items-center gap-3">
          <h3 className="font-medium text-text-strong">Status</h3>
          <StatusBadge status={session.status} />
        </div>
        <dl className="grid gap-1 text-sm sm:grid-cols-2">
          <div>
            <dt className="inline text-text-muted">Kind: </dt>
            <dd className="inline capitalize">{session.kind}</dd>
          </div>
          <div>
            <dt className="inline text-text-muted">Structure: </dt>
            <dd className="inline">{perGroup ? "One bank per group" : "Single bank"}</dd>
          </div>
          <div>
            <dt className="inline text-text-muted">Opened: </dt>
            <dd className="inline">{formatDateTime(session.opened_at)}</dd>
          </div>
          <div>
            <dt className="inline text-text-muted">Archived: </dt>
            <dd className="inline">{formatDateTime(session.archived_at)}</dd>
          </div>
        </dl>
        {session.status === "draft" && (
          <div className="flex flex-wrap items-end gap-3">
            {perGroup && (
              <Labeled label="Number of groups" error={groupErr ?? undefined}>
                <TextInput
                  type="number"
                  min={1}
                  value={groups}
                  onChange={(e) => setGroups(e.target.value)}
                  className="w-32"
                />
              </Labeled>
            )}
            <Button disabled={t.isPending} onClick={open}>
              {t.isPending ? "Opening…" : "Open session"}
            </Button>
          </div>
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
        <ErrorMsg error={t.error} />
      </section>
      <section className="space-y-3">
        <h3 className="font-medium text-text-strong">Business date per bank</h3>
        <QueryState query={days}>
          {days.data?.length ? (
            <Table>
              <thead>
                <tr>
                  <Th>Bank</Th>
                  <Th>Business date</Th>
                  <Th>Day status</Th>
                </tr>
              </thead>
              <tbody>
                {days.data.map((d) => (
                  <tr key={d.bank_id} className="hover:bg-hover">
                    <Td className="font-medium text-text-strong">{d.bank_name}</Td>
                    <Td>{d.date}</Td>
                    <Td>
                      <StatusBadge status={d.status} />
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          ) : (
            <Empty>Business days appear once the session is open.</Empty>
          )}
        </QueryState>
      </section>
    </div>
  );
}
