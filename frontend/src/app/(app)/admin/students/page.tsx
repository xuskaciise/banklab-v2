"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import type { ColumnDef } from "@tanstack/react-table";
import { Pencil, Search } from "lucide-react";
import { useAdminStudents, useRenameStudent } from "@/lib/admin";
import type { AdminStudentOut } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { DataTable } from "@/components/shared/data-table";
import { PageHeader } from "@/components/shared/page-header";
import { StatusBadge } from "@/components/shared/status-badge";
import { ErrorMsg, Labeled, TextInput } from "@/components/lab/common";

const ID_FORMAT = /^[A-Za-z0-9][A-Za-z0-9._-]{2,29}$/;
const ID_HINT =
  "3-30 letters, digits, dot, underscore or hyphen. Must start with a letter or digit.";

function RenameDialog({
  student,
  onClose,
}: {
  student: AdminStudentOut | null;
  onClose: () => void;
}) {
  return (
    <Dialog open={!!student} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        {student && (
          <RenameBody key={student.id} student={student} onClose={onClose} />
        )}
      </DialogContent>
    </Dialog>
  );
}

function RenameBody({
  student,
  onClose,
}: {
  student: AdminStudentOut;
  onClose: () => void;
}) {
  const rename = useRenameStudent();
  const [value, setValue] = useState(student.username);
  const [error, setError] = useState<string>();
  const [confirming, setConfirming] = useState(false);

  function next(ev: React.FormEvent) {
    ev.preventDefault();
    const v = value.trim();
    if (!ID_FORMAT.test(v)) return setError(ID_HINT);
    if (v === student.username) return setError("Enter a different Student ID");
    setError(undefined);
    rename.reset();
    setConfirming(true);
  }

  function save() {
    rename.mutate(
      { id: student.id, username: value.trim() },
      {
        onSuccess: (u) => {
          toast.success(`Student ID changed to ${u.username}`);
          onClose();
        },
        onError: () => setConfirming(false),
      },
    );
  }

  return (
    <>
      {confirming ? (
        <>
          <DialogHeader>
            <DialogTitle>Change Student ID?</DialogTitle>
            <DialogDescription>
              {student.full_name}: {student.username} → {value.trim()}. The
              student must log in with the new ID. Their old ID will stop
              working.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              disabled={rename.isPending}
              onClick={() => setConfirming(false)}
            >
              Back
            </Button>
            <Button disabled={rename.isPending} onClick={save}>
              {rename.isPending ? "Saving…" : "Confirm and save"}
            </Button>
          </DialogFooter>
        </>
      ) : (
        <form onSubmit={next} noValidate className="flex min-h-0 flex-col">
          <DialogHeader>
            <DialogTitle>Edit Student ID</DialogTitle>
            <DialogDescription>{student.full_name}</DialogDescription>
          </DialogHeader>
          <DialogBody className="space-y-4">
            <Labeled label="Student ID" required error={error} hint={ID_HINT}>
              <TextInput
                autoFocus
                value={value}
                onChange={(e) => setValue(e.target.value)}
                autoComplete="off"
              />
            </Labeled>
            <ErrorMsg error={rename.error} />
          </DialogBody>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit">Save</Button>
          </DialogFooter>
        </form>
      )}
    </>
  );
}

export default function AdminStudentsPage() {
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [editing, setEditing] = useState<AdminStudentOut | null>(null);
  const list = useAdminStudents(q);

  useEffect(() => {
    const t = setTimeout(() => setQ(search.trim()), 300);
    return () => clearTimeout(t);
  }, [search]);

  const columns: ColumnDef<AdminStudentOut>[] = [
    {
      accessorKey: "username",
      header: "Student ID",
      meta: { label: "Student ID" },
    },
    {
      accessorKey: "full_name",
      header: "Full name",
      meta: { label: "Full name" },
    },
    { accessorKey: "phone", header: "Phone", meta: { label: "Phone" } },
    {
      accessorKey: "is_active",
      header: "Status",
      meta: { label: "Status" },
      cell: ({ row }) => (
        <StatusBadge
          status={row.original.is_active ? "active" : "inactive"}
          label={row.original.is_active ? "Active" : "Inactive"}
        />
      ),
    },
    {
      id: "actions",
      header: "",
      enableSorting: false,
      meta: { label: "Actions", className: "text-right" },
      cell: ({ row }) => (
        <div className="flex justify-end">
          <Button
            size="sm"
            variant="outline"
            onClick={() => setEditing(row.original)}
          >
            <Pencil /> Edit Student ID
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="mx-auto w-full max-w-5xl">
      <PageHeader
        title="Students"
        subtitle="Find a student and correct their Student ID. Shows up to 200 matches."
      />
      <DataTable
        columns={columns}
        data={list.data}
        isLoading={list.isPending}
        error={list.error}
        getRowId={(r) => r.id}
        hideSearch
        filters={
          <div className="relative min-w-0 flex-1 sm:max-w-xs">
            <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-text-muted" />
            <Input
              aria-label="Search students"
              placeholder="Search by ID, name or phone…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-8 pl-8"
            />
          </div>
        }
        emptyTitle={q ? "No matching students" : "No students yet"}
        emptyDescription={q ? "Try a different search term." : undefined}
        columnToggle={false}
        fit
      />
      <RenameDialog student={editing} onClose={() => setEditing(null)} />
    </div>
  );
}
