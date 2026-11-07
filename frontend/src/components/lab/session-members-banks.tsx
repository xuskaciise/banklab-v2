"use client";

import { useMemo, useState } from "react";
import type { ColumnDef, RowSelectionState } from "@tanstack/react-table";
import {
  Building2,
  MoreHorizontal,
  Pencil,
  Plus,
  Search,
  UserCheck,
  UserMinus,
  Users,
} from "lucide-react";
import { toast } from "sonner";
import type {
  BankOut,
  MemberOut,
  SessionOut,
  StudentOut,
} from "@/lib/api/types";
import {
  ROLE_LABEL,
  roleLabel,
  useAddBank,
  useAddMembers,
  useAssignRole,
  useBanks,
  useMemberVisibility,
  useMembers,
  useMoveMember,
  useStudents,
} from "@/lib/lab";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input, Select } from "@/components/ui/input";
import { Avatar } from "@/components/shared/avatar";
import { Checkbox } from "@/components/shared/checkbox";
import { DataTable } from "@/components/shared/data-table";
import { StatCard } from "@/components/shared/stat-card";
import { StatusBadge } from "@/components/shared/status-badge";
import { ErrorMsg, Labeled, QueryState } from "./common";

const visLabel = (v?: string | null) =>
  v === "own" ? "Own work only" : v === "all" ? "Whole bank" : "Session default";

// ---------------- Edit one member ----------------
function EditMemberDialog({
  m,
  session,
  banks,
  open,
  onOpenChange,
}: {
  m: MemberOut;
  session: SessionOut;
  banks: BankOut[];
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const move = useMoveMember(session.id);
  const role = useAssignRole(session.id);
  const vis = useMemberVisibility(session.id);
  const exam = session.kind === "exam";
  const [bankId, setBankId] = useState(m.bank_id ?? "");
  const [roleV, setRoleV] = useState(m.role ?? "");
  const [visV, setVisV] = useState(m.visibility_override ?? "");
  const pending = move.isPending || role.isPending || vis.isPending;
  const err = move.error ?? role.error ?? vis.error;

  async function save() {
    try {
      if (bankId && bankId !== (m.bank_id ?? ""))
        await move.mutateAsync({ memberId: m.id, bank_id: bankId });
      if (roleV && roleV !== (m.role ?? ""))
        await role.mutateAsync({ memberId: m.id, role: roleV });
      if (!exam && visV !== (m.visibility_override ?? ""))
        await vis.mutateAsync({ memberId: m.id, visibility: visV || null });
      toast.success(`${m.full_name} updated`);
      onOpenChange(false);
    } catch {
      /* error shown in dialog */
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        onOpenChange(v);
        if (!v) {
          move.reset();
          role.reset();
          vis.reset();
          setBankId(m.bank_id ?? "");
          setRoleV(m.role ?? "");
          setVisV(m.visibility_override ?? "");
        }
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit member</DialogTitle>
          <DialogDescription>
            {m.full_name} · {m.username}
          </DialogDescription>
        </DialogHeader>
        <DialogBody className="space-y-4">
          <Labeled label="Bank / group">
            <Select value={bankId} onChange={(e) => setBankId(e.target.value)}>
              <option value="" disabled>
                Unplaced
              </option>
              {banks.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </Select>
          </Labeled>
          <Labeled label="Role">
            <Select value={roleV} onChange={(e) => setRoleV(e.target.value)}>
              <option value="" disabled>
                No role
              </option>
              {session.allowed_roles.map((r) => (
                <option key={r} value={r}>
                  {ROLE_LABEL[r] ?? r}
                </option>
              ))}
            </Select>
          </Labeled>
          <Labeled
            label="Visibility"
            hint={exam ? "Exams always use own work only." : undefined}
          >
            <Select
              value={exam ? "own" : visV}
              disabled={exam}
              onChange={(e) => setVisV(e.target.value)}
            >
              <option value="">Session default</option>
              <option value="own">Own work only</option>
              <option value="all">Whole bank</option>
            </Select>
          </Labeled>
          <ErrorMsg error={err} />
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button disabled={pending} onClick={save}>
            {pending ? "Saving…" : "Save changes"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function MemberActions({
  m,
  session,
  banks,
}: {
  m: MemberOut;
  session: SessionOut;
  banks: BankOut[];
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger
          aria-label={`Actions for ${m.full_name}`}
          render={
            <Button variant="ghost" size="icon-sm">
              <MoreHorizontal />
            </Button>
          }
        />
        <DropdownMenuContent>
          <DropdownMenuItem onClick={() => setOpen(true)}>
            <Pencil /> Edit placement and role
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <EditMemberDialog
        m={m}
        session={session}
        banks={banks}
        open={open}
        onOpenChange={setOpen}
      />
    </>
  );
}

// ---------------- Add students ----------------
function AddMembersDialog({
  session,
  existing,
  banks,
}: {
  session: SessionOut;
  existing: MemberOut[];
  banks: BankOut[];
}) {
  const students = useStudents(session.class_id);
  const add = useAddMembers(session.id);
  const [open, setOpen] = useState(false);
  const [picked, setPicked] = useState<string[]>([]);
  const [bankId, setBankId] = useState("");
  const [q, setQ] = useState("");
  const taken = new Set(existing.map((m) => m.user_id));
  const available = (students.data ?? []).filter(
    (s) => s.is_active && !taken.has(s.id),
  );
  const shown = available.filter((s: StudentOut) =>
    `${s.full_name} ${s.username}`.toLowerCase().includes(q.trim().toLowerCase()),
  );
  const toggle = (id: string) =>
    setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));
  const allShown = shown.length > 0 && shown.every((s) => picked.includes(s.id));

  function change(v: boolean) {
    setOpen(v);
    if (!v) {
      add.reset();
      setPicked([]);
      setQ("");
    }
  }
  const done = (n: number | string) => () => {
    toast.success(`${n} student(s) added to the session`);
    change(false);
  };

  return (
    <>
      <Button size="sm" onClick={() => setOpen(true)}>
        <Plus /> Add students
      </Button>
      <Dialog open={open} onOpenChange={change}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Add students</DialogTitle>
            <DialogDescription>
              Choose enrolled students to add to this session.
            </DialogDescription>
          </DialogHeader>
          <DialogBody className="space-y-4">
            <QueryState query={students}>
              {available.length === 0 ? (
                <p className="flex items-center gap-2 rounded-lg bg-hover px-3 py-3 text-sm text-text-muted">
                  <UserCheck className="size-4 shrink-0" />
                  All active enrolled students are already members.
                </p>
              ) : (
                <>
                  <div className="relative">
                    <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-text-muted" />
                    <Input
                      aria-label="Search students"
                      placeholder="Search by name or ID…"
                      value={q}
                      onChange={(e) => setQ(e.target.value)}
                      className="pl-8"
                    />
                  </div>
                  <div className="overflow-hidden rounded-lg border border-border">
                    <label className="flex cursor-pointer items-center gap-3 border-b border-border bg-surface px-3 py-2 text-xs font-medium text-text-muted">
                      <Checkbox
                        checked={allShown}
                        onChange={() =>
                          setPicked((p) =>
                            allShown
                              ? p.filter((id) => !shown.some((s) => s.id === id))
                              : Array.from(
                                  new Set([...p, ...shown.map((s) => s.id)]),
                                ),
                          )
                        }
                      />
                      Select all shown ({shown.length})
                    </label>
                    <ul className="max-h-64 divide-y divide-border overflow-y-auto">
                      {shown.map((s) => (
                        <li key={s.id}>
                          <label className="flex cursor-pointer items-center gap-3 px-3 py-2 hover:bg-hover">
                            <Checkbox
                              checked={picked.includes(s.id)}
                              onChange={() => toggle(s.id)}
                            />
                            <Avatar name={s.full_name} className="size-7" />
                            <span className="min-w-0 text-sm">
                              <span className="block truncate font-medium text-text-strong">
                                {s.full_name}
                              </span>
                              <span className="block font-mono text-xs text-text-muted">
                                {s.username}
                              </span>
                            </span>
                          </label>
                        </li>
                      ))}
                      {shown.length === 0 && (
                        <li className="px-3 py-6 text-center text-sm text-text-muted">
                          No students match your search.
                        </li>
                      )}
                    </ul>
                  </div>
                  <Labeled label="Place in bank">
                    <Select
                      value={bankId}
                      onChange={(e) => setBankId(e.target.value)}
                    >
                      <option value="">Unplaced</option>
                      {banks.map((b) => (
                        <option key={b.id} value={b.id}>
                          {b.name}
                        </option>
                      ))}
                    </Select>
                  </Labeled>
                </>
              )}
            </QueryState>
            <ErrorMsg error={add.error} />
          </DialogBody>
          {available.length > 0 && (
            <DialogFooter>
              <Button
                variant="outline"
                disabled={add.isPending}
                onClick={() =>
                  add.mutate(
                    { user_ids: [], all_enrolled: true, bank_id: bankId || null },
                    { onSuccess: done("All enrolled") },
                  )
                }
              >
                Add all enrolled
              </Button>
              <Button
                disabled={add.isPending || picked.length === 0}
                onClick={() =>
                  add.mutate(
                    {
                      user_ids: picked,
                      all_enrolled: false,
                      bank_id: bankId || null,
                    },
                    { onSuccess: done(picked.length) },
                  )
                }
              >
                {add.isPending ? "Adding…" : `Add selected (${picked.length})`}
              </Button>
            </DialogFooter>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}

// ---------------- Members tab ----------------
export function MembersTab({
  session,
  readOnly,
}: {
  session: SessionOut;
  readOnly: boolean;
}) {
  const members = useMembers(session.id);
  const banks = useBanks(session.id);
  const move = useMoveMember(session.id);
  const role = useAssignRole(session.id);
  const [bankFilter, setBankFilter] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [selection, setSelection] = useState<RowSelectionState>({});
  const [bulkBank, setBulkBank] = useState("");
  const [bulkRole, setBulkRole] = useState("");
  const [bulkBusy, setBulkBusy] = useState(false);

  const all = members.data;
  const bankList = useMemo(() => banks.data ?? [], [banks.data]);
  const rolesAssigned = all?.filter((m) => m.role).length ?? 0;
  const filtered = useMemo(
    () =>
      all?.filter(
        (m) =>
          (!bankFilter ||
            (bankFilter === "none" ? !m.bank_id : m.bank_id === bankFilter)) &&
          (!roleFilter ||
            (roleFilter === "none" ? !m.role : m.role === roleFilter)),
      ),
    [all, bankFilter, roleFilter],
  );
  const selectedIds = Object.keys(selection).filter((k) => selection[k]);

  async function applyBulk() {
    setBulkBusy(true);
    const jobs = selectedIds.flatMap((id) => [
      ...(bulkBank ? [move.mutateAsync({ memberId: id, bank_id: bulkBank })] : []),
      ...(bulkRole ? [role.mutateAsync({ memberId: id, role: bulkRole })] : []),
    ]);
    const res = await Promise.allSettled(jobs);
    const failed = res.filter((r) => r.status === "rejected").length;
    setBulkBusy(false);
    if (failed) toast.error(`${failed} change(s) failed. The rest were applied.`);
    else toast.success(`Updated ${selectedIds.length} member(s)`);
    setSelection({});
    setBulkBank("");
    setBulkRole("");
  }

  const columns: ColumnDef<MemberOut>[] = [
    ...(readOnly
      ? []
      : [
          {
            id: "select",
            enableSorting: false,
            enableHiding: false,
            meta: { className: "w-10", label: "Select" },
            header: ({ table }) => (
              <Checkbox
                aria-label="Select all rows"
                checked={table.getIsAllPageRowsSelected()}
                onChange={table.getToggleAllPageRowsSelectedHandler()}
              />
            ),
            cell: ({ row }) => (
              <Checkbox
                aria-label={`Select ${row.original.full_name}`}
                checked={row.getIsSelected()}
                onChange={row.getToggleSelectedHandler()}
              />
            ),
          } as ColumnDef<MemberOut>,
        ]),
    {
      id: "student",
      header: "Student",
      accessorFn: (m) => `${m.full_name} ${m.username}`,
      meta: { label: "Student" },
      cell: ({ row }) => (
        <div className="flex items-center gap-3">
          <Avatar name={row.original.full_name} />
          <div className="min-w-0">
            <p className="truncate font-medium text-text-strong">
              {row.original.full_name}
            </p>
            <p className="font-mono text-xs text-text-muted">
              {row.original.username}
            </p>
          </div>
        </div>
      ),
    },
    {
      id: "bank",
      header: "Bank / group",
      accessorFn: (m) => m.bank_name ?? "Unplaced",
      cell: ({ row }) =>
        row.original.bank_name ? (
          <span className="inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-2 py-0.5 text-xs font-medium text-text-strong">
            <Building2 className="size-3 text-text-muted" />
            {row.original.bank_name}
          </span>
        ) : (
          <StatusBadge status="unplaced" tone="pending" label="Unplaced" />
        ),
    },
    {
      id: "role",
      header: "Role",
      accessorFn: (m) => roleLabel(m.role),
      cell: ({ row }) =>
        row.original.role ? (
          <StatusBadge
            status={row.original.role}
            tone="info"
            label={roleLabel(row.original.role)}
          />
        ) : (
          <StatusBadge status="no_role" tone="muted" label="No role" />
        ),
    },
    {
      id: "visibility",
      header: "Visibility",
      accessorFn: (m) =>
        session.kind === "exam"
          ? "Own work only (exam)"
          : visLabel(m.visibility_override),
      cell: ({ getValue }) => (
        <span className="text-text-muted">{getValue<string>()}</span>
      ),
    },
    ...(readOnly
      ? []
      : [
          {
            id: "actions",
            header: () => <span className="sr-only">Actions</span>,
            enableSorting: false,
            enableHiding: false,
            meta: { className: "w-12 text-right" },
            cell: ({ row }) => (
              <MemberActions m={row.original} session={session} banks={bankList} />
            ),
          } as ColumnDef<MemberOut>,
        ]),
  ];

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Members"
          icon={Users}
          loading={members.isPending}
          value={all?.length ?? 0}
        />
        <StatCard
          label="Banks"
          icon={Building2}
          loading={banks.isPending}
          value={bankList.length}
        />
        <StatCard
          label="Roles assigned"
          icon={UserCheck}
          loading={members.isPending}
          value={rolesAssigned}
        />
        <StatCard
          label="Unassigned"
          icon={UserMinus}
          loading={members.isPending}
          value={(all?.length ?? 0) - rolesAssigned}
          hint="Members without a role"
        />
      </div>

      {selectedIds.length > 0 && !readOnly && (
        <div
          role="region"
          aria-label="Bulk actions"
          className="flex flex-wrap items-center gap-3 rounded-xl border border-bank-accent/40 bg-bank-sky-light px-4 py-3"
        >
          <span className="text-sm font-medium text-bank-primary">
            {selectedIds.length} selected
          </span>
          <Select
            aria-label="Bulk bank"
            value={bulkBank}
            onChange={(e) => setBulkBank(e.target.value)}
            className="h-8 w-44"
          >
            <option value="">Move to bank…</option>
            {bankList.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </Select>
          <Select
            aria-label="Bulk role"
            value={bulkRole}
            onChange={(e) => setBulkRole(e.target.value)}
            className="h-8 w-48"
          >
            <option value="">Assign role…</option>
            {session.allowed_roles.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABEL[r] ?? r}
              </option>
            ))}
          </Select>
          <Button
            size="sm"
            disabled={bulkBusy || (!bulkBank && !bulkRole)}
            onClick={applyBulk}
          >
            {bulkBusy ? "Applying…" : "Apply"}
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setSelection({})}>
            Clear
          </Button>
        </div>
      )}

      <DataTable
        columns={columns}
        data={filtered}
        isLoading={members.isPending}
        error={members.error}
        getRowId={(m) => m.id}
        searchPlaceholder="Search students…"
        rowSelection={readOnly ? undefined : selection}
        onRowSelectionChange={setSelection}
        filters={
          <>
            <Select
              aria-label="Filter by bank"
              value={bankFilter}
              onChange={(e) => setBankFilter(e.target.value)}
              className="h-8 w-40"
            >
              <option value="">All banks</option>
              <option value="none">Unplaced</option>
              {bankList.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </Select>
            <Select
              aria-label="Filter by role"
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="h-8 w-44"
            >
              <option value="">All roles</option>
              <option value="none">No role</option>
              {session.allowed_roles.map((r) => (
                <option key={r} value={r}>
                  {ROLE_LABEL[r] ?? r}
                </option>
              ))}
            </Select>
          </>
        }
        toolbar={
          readOnly ? undefined : (
            <AddMembersDialog
              session={session}
              existing={all ?? []}
              banks={bankList}
            />
          )
        }
        emptyTitle="No members yet"
        emptyDescription="Add enrolled students to this session, then place them in banks and give them roles."
        emptyAction={
          readOnly ? undefined : (
            <AddMembersDialog
              session={session}
              existing={all ?? []}
              banks={bankList}
            />
          )
        }
      />
    </div>
  );
}

// ---------------- Banks tab ----------------
export function BanksTab({
  session,
  readOnly,
}: {
  session: SessionOut;
  readOnly: boolean;
}) {
  const banks = useBanks(session.id);
  const members = useMembers(session.id);
  const addBank = useAddBank(session.id);
  const canAdd =
    !readOnly && session.structure === "per_group" && session.status === "active";
  const counts = new Map<string, number>();
  for (const m of members.data ?? [])
    if (m.bank_id) counts.set(m.bank_id, (counts.get(m.bank_id) ?? 0) + 1);

  const columns: ColumnDef<BankOut>[] = [
    {
      accessorKey: "name",
      header: "Bank",
      cell: ({ row }) => (
        <span className="flex items-center gap-3">
          <span className="flex size-8 items-center justify-center rounded-lg bg-bank-sky-light text-bank-primary">
            <Building2 className="size-4" />
          </span>
          <span className="font-medium text-text-strong">{row.original.name}</span>
        </span>
      ),
    },
    {
      id: "group",
      header: "Group",
      accessorFn: (b) => b.group_no ?? 0,
      cell: ({ row }) => row.original.group_no ?? "—",
    },
    {
      id: "members",
      header: "Members",
      accessorFn: (b) => counts.get(b.id) ?? 0,
      cell: ({ getValue }) => (
        <span className="tabular-nums">{getValue<number>()}</span>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-xl text-sm text-text-muted">
          {session.structure === "per_group"
            ? "Each group runs its own bank with its own business date. Add a group bank while the session is open."
            : "This session uses a single bank shared by all members."}
        </p>
        {canAdd && (
          <Button
            disabled={addBank.isPending}
            onClick={() =>
              addBank.mutate(undefined, {
                onSuccess: () => toast.success("Group bank added"),
              })
            }
          >
            <Plus /> {addBank.isPending ? "Adding…" : "Add group bank"}
          </Button>
        )}
      </div>
      <ErrorMsg error={addBank.error} />
      <DataTable
        columns={columns}
        data={banks.data}
        isLoading={banks.isPending}
        error={banks.error}
        getRowId={(b) => b.id}
        searchPlaceholder="Search banks…"
        columnToggle={false}
        emptyTitle="No banks yet"
        emptyDescription="Banks are created when the session is opened."
      />
    </div>
  );
}
