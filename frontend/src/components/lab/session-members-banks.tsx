"use client";

import { useState } from "react";
import type { MemberOut, SessionOut } from "@/lib/api/types";
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
  Empty,
  ErrorMsg,
  QueryState,
  Select,
  Table,
  Td,
  Th,
} from "./common";
import type { BankOut } from "@/lib/api/types";

function MemberRow({
  m,
  session,
  banks,
  readOnly,
}: {
  m: MemberOut;
  session: SessionOut;
  banks: BankOut[];
  readOnly: boolean;
}) {
  const move = useMoveMember(session.id);
  const vis = useMemberVisibility(session.id);
  const role = useAssignRole(session.id);
  const exam = session.kind === "exam";
  return (
    <tr className="hover:bg-hover">
      <Td>
        <div className="font-medium text-text-strong">{m.full_name}</div>
        <div className="text-xs text-text-muted">{m.username}</div>
      </Td>
      <Td>
        {readOnly ? (
          (m.bank_name ?? "Unplaced")
        ) : (
          <Select
            aria-label={`Bank for ${m.full_name}`}
            value={m.bank_id ?? ""}
            disabled={move.isPending}
            onChange={(e) =>
              e.target.value &&
              move.mutate({ memberId: m.id, bank_id: e.target.value })
            }
          >
            <option value="" disabled>
              Unplaced
            </option>
            {banks.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </Select>
        )}
      </Td>
      <Td>
        {readOnly ? (
          roleLabel(m.role)
        ) : (
          <Select
            aria-label={`Role for ${m.full_name}`}
            value={m.role ?? ""}
            disabled={role.isPending}
            onChange={(e) =>
              e.target.value &&
              role.mutate({ memberId: m.id, role: e.target.value })
            }
          >
            <option value="" disabled>
              No role
            </option>
            {session.allowed_roles.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABEL[r] ?? r}
              </option>
            ))}
          </Select>
        )}
      </Td>
      <Td>
        {exam ? (
          "Own work only (exam)"
        ) : readOnly ? (
          (m.visibility_override ?? "Session default")
        ) : (
          <Select
            aria-label={`Visibility for ${m.full_name}`}
            value={m.visibility_override ?? ""}
            disabled={vis.isPending}
            onChange={(e) =>
              vis.mutate({ memberId: m.id, visibility: e.target.value || null })
            }
          >
            <option value="">Session default</option>
            <option value="own">Own work only</option>
            <option value="all">Whole bank</option>
          </Select>
        )}
        <ErrorMsg error={move.error ?? vis.error ?? role.error} />
      </Td>
    </tr>
  );
}

function AddMembers({
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
  const [picked, setPicked] = useState<string[]>([]);
  const [bankId, setBankId] = useState("");
  const taken = new Set(existing.map((m) => m.user_id));
  const available = (students.data ?? []).filter(
    (s) => s.is_active && !taken.has(s.id),
  );
  const toggle = (id: string) =>
    setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));

  return (
    <div className="space-y-3 rounded-lg border border-border bg-card p-4">
      <h3 className="font-medium text-text-strong">Add students</h3>
      <QueryState query={students}>
        {available.length === 0 ? (
          <p className="text-sm text-text-muted">
            All active enrolled students are already members.
          </p>
        ) : (
          <>
            <div className="grid max-h-48 gap-1 overflow-y-auto sm:grid-cols-2">
              {available.map((s) => (
                <label key={s.id} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={picked.includes(s.id)}
                    onChange={() => toggle(s.id)}
                    className="size-4 accent-bank-primary"
                  />
                  {s.full_name}{" "}
                  <span className="text-text-muted">({s.username})</span>
                </label>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Select
                aria-label="Place in bank"
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
              <Button
                disabled={add.isPending || picked.length === 0}
                onClick={() =>
                  add.mutate(
                    {
                      user_ids: picked,
                      all_enrolled: false,
                      bank_id: bankId || null,
                    },
                    { onSuccess: () => setPicked([]) },
                  )
                }
              >
                Add selected ({picked.length})
              </Button>
              <Button
                variant="outline"
                disabled={add.isPending}
                onClick={() =>
                  add.mutate({
                    user_ids: [],
                    all_enrolled: true,
                    bank_id: bankId || null,
                  })
                }
              >
                Add all enrolled
              </Button>
            </div>
          </>
        )}
      </QueryState>
      <ErrorMsg error={add.error} />
    </div>
  );
}

export function MembersTab({
  session,
  readOnly,
}: {
  session: SessionOut;
  readOnly: boolean;
}) {
  const members = useMembers(session.id);
  const banks = useBanks(session.id);
  return (
    <div className="space-y-4">
      {!readOnly && (
        <AddMembers
          session={session}
          existing={members.data ?? []}
          banks={banks.data ?? []}
        />
      )}
      <QueryState query={members}>
        {members.data?.length ? (
          <Table>
            <thead>
              <tr>
                <Th>Student</Th>
                <Th>Bank / group</Th>
                <Th>Active role</Th>
                <Th>Visibility</Th>
              </tr>
            </thead>
            <tbody>
              {members.data.map((m) => (
                <MemberRow
                  key={m.id}
                  m={m}
                  session={session}
                  banks={banks.data ?? []}
                  readOnly={readOnly}
                />
              ))}
            </tbody>
          </Table>
        ) : (
          <Empty>No members yet. Add students from the class above.</Empty>
        )}
      </QueryState>
    </div>
  );
}

export function BanksTab({
  session,
  readOnly,
}: {
  session: SessionOut;
  readOnly: boolean;
}) {
  const banks = useBanks(session.id);
  const addBank = useAddBank(session.id);
  const canAdd =
    !readOnly && session.structure === "per_group" && session.status === "active";
  return (
    <div className="space-y-4">
      {canAdd && (
        <div>
          <Button disabled={addBank.isPending} onClick={() => addBank.mutate()}>
            {addBank.isPending ? "Adding…" : "Add group bank"}
          </Button>
        </div>
      )}
      <ErrorMsg error={addBank.error} />
      <QueryState query={banks}>
        {banks.data?.length ? (
          <Table>
            <thead>
              <tr>
                <Th>Bank</Th>
                <Th>Group</Th>
              </tr>
            </thead>
            <tbody>
              {banks.data.map((b) => (
                <tr key={b.id} className="hover:bg-hover">
                  <Td className="font-medium text-text-strong">{b.name}</Td>
                  <Td>{b.group_no ?? "—"}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        ) : (
          <Empty>
            No banks yet. Banks are created when the session is opened.
          </Empty>
        )}
      </QueryState>
    </div>
  );
}
