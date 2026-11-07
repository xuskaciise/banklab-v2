"use client";

import { useState } from "react";
import Link from "next/link";
import type { StudentOut } from "@/lib/api/types";
import {
  useAddStudent,
  useResetStudentPassword,
  useStudents,
  useUpdateStudent,
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

const PHONE_DIGITS = /^\d{7,12}$/;
const phoneOk = (v: string) => PHONE_DIGITS.test(v.replace(/[\s+()-]/g, ""));

function AddStudentForm({ classId }: { classId: string }) {
  const add = useAddStudent(classId);
  const [username, setUsername] = useState("");
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [errors, setErrors] = useState<Record<string, string | undefined>>({});
  const [note, setNote] = useState<string | null>(null);

  function submit(ev: React.FormEvent) {
    ev.preventDefault();
    const next = {
      username: username.trim() ? undefined : "Enter the Student ID",
      full_name: fullName.trim() ? undefined : "Enter the full name",
      phone: phoneOk(phone) ? undefined : "Phone must have 7 to 12 digits",
    };
    setErrors(next);
    setNote(null);
    if (next.username || next.full_name || next.phone) return;
    add.mutate(
      { username: username.trim(), full_name: fullName.trim(), phone: phone.trim() },
      {
        onSuccess: (r) => {
          setNote(
            r.created
              ? `${r.student.full_name} was created and enrolled.`
              : `${r.student.full_name} was enrolled.`,
          );
          setUsername("");
          setFullName("");
          setPhone("");
        },
      },
    );
  }

  return (
    <form
      onSubmit={submit}
      noValidate
      className="grid gap-3 rounded-lg border border-border bg-card p-4 sm:grid-cols-3"
    >
      <Labeled label="Student ID" error={errors.username}>
        <TextInput value={username} onChange={(e) => setUsername(e.target.value)} />
      </Labeled>
      <Labeled label="Full name" error={errors.full_name}>
        <TextInput value={fullName} onChange={(e) => setFullName(e.target.value)} />
      </Labeled>
      <Labeled label="Phone" error={errors.phone}>
        <TextInput
          inputMode="tel"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
        />
      </Labeled>
      <div className="space-y-2 sm:col-span-3">
        <ErrorMsg error={add.error} />
        {note && (
          <p role="status" className="text-sm text-fin-success-dark">
            {note}
          </p>
        )}
        <Button type="submit" disabled={add.isPending}>
          {add.isPending ? "Adding…" : "Add student"}
        </Button>
      </div>
    </form>
  );
}

function StudentRow({ classId, s }: { classId: string; s: StudentOut }) {
  const update = useUpdateStudent(classId);
  const reset = useResetStudentPassword(classId);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(s.full_name);
  const [phone, setPhone] = useState(s.phone);
  const [err, setErr] = useState<string | null>(null);
  const [resetDone, setResetDone] = useState(false);

  function save() {
    if (!name.trim()) return setErr("Name is required");
    if (!phoneOk(phone)) return setErr("Phone must have 7 to 12 digits");
    setErr(null);
    update.mutate(
      { userId: s.id, body: { full_name: name.trim(), phone: phone.trim() } },
      { onSuccess: () => setEditing(false) },
    );
  }

  return (
    <tr className="hover:bg-hover">
      <Td className="text-text-muted">{s.username}</Td>
      <Td>
        {editing ? (
          <TextInput value={name} onChange={(e) => setName(e.target.value)} />
        ) : (
          <span className="font-medium text-text-strong">{s.full_name}</span>
        )}
      </Td>
      <Td>
        {editing ? (
          <TextInput value={phone} onChange={(e) => setPhone(e.target.value)} />
        ) : (
          s.phone
        )}
      </Td>
      <Td>
        <StatusBadge
          status={s.is_active ? "active" : "inactive"}
          label={s.is_active ? "Active" : "Inactive"}
        />
      </Td>
      <Td>
        <div className="flex flex-wrap items-center gap-2">
          {editing ? (
            <>
              <Button size="sm" disabled={update.isPending} onClick={save}>
                Save
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setEditing(false);
                  setName(s.full_name);
                  setPhone(s.phone);
                  setErr(null);
                }}
              >
                Cancel
              </Button>
            </>
          ) : (
            <>
              <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
                Edit
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={update.isPending}
                onClick={() =>
                  update.mutate({ userId: s.id, body: { is_active: !s.is_active } })
                }
              >
                {s.is_active ? "Deactivate" : "Activate"}
              </Button>
              <ConfirmButton
                label="Reset password"
                confirmLabel="Reset"
                message={`Reset ${s.full_name}'s password to the last 4 digits of their phone?`}
                pending={reset.isPending}
                onConfirm={() =>
                  reset.mutate(s.id, { onSuccess: () => setResetDone(true) })
                }
              />
            </>
          )}
        </div>
        {err && <p className="mt-1 text-sm text-fin-danger">{err}</p>}
        <ErrorMsg error={update.error ?? reset.error} />
        {resetDone && !reset.error && (
          <p role="status" className="mt-1 text-sm text-fin-success-dark">
            Password reset. The student must change it at next login.
          </p>
        )}
      </Td>
    </tr>
  );
}

export function StudentsTab({ classId }: { classId: string }) {
  const students = useStudents(classId);
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-text-strong">Students</h2>
        <Link href={`/instructor/classes/${classId}/import`}>
          <Button variant="outline">Import from CSV</Button>
        </Link>
      </div>
      <AddStudentForm classId={classId} />
      <QueryState query={students}>
        {students.data?.length ? (
          <Table>
            <thead>
              <tr>
                <Th>Student ID</Th>
                <Th>Name</Th>
                <Th>Phone</Th>
                <Th>Status</Th>
                <Th>Actions</Th>
              </tr>
            </thead>
            <tbody>
              {students.data.map((s) => (
                <StudentRow key={s.id} classId={classId} s={s} />
              ))}
            </tbody>
          </Table>
        ) : (
          <Empty>No students yet. Add one above or import a CSV file.</Empty>
        )}
      </QueryState>
    </div>
  );
}
