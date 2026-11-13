"use client";

import { useState } from "react";
import Link from "next/link";
import type { ColumnDef } from "@tanstack/react-table";
import {
  KeyRound,
  MoreHorizontal,
  Pencil,
  Plus,
  Power,
  Upload,
} from "lucide-react";
import { toast } from "sonner";
import type { StudentOut } from "@/lib/api/types";
import {
  useAddStudent,
  useResetStudentPassword,
  useStudents,
  useUpdateStudent,
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
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { DataTable } from "@/components/shared/data-table";
import { StatusBadge } from "@/components/shared/status-badge";
import { ErrorMsg, Labeled, TextInput } from "./common";

const PHONE_DIGITS = /^\d{7,12}$/;
const phoneOk = (v: string) => PHONE_DIGITS.test(v.replace(/[\s+()-]/g, ""));

function AddStudentDialog({
  classId,
  open,
  onOpenChange,
}: {
  classId: string;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const add = useAddStudent(classId);
  const [username, setUsername] = useState("");
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [errors, setErrors] = useState<Record<string, string | undefined>>({});

  function change(v: boolean) {
    onOpenChange(v);
    if (!v) {
      add.reset();
      setErrors({});
    }
  }

  function submit(ev: React.FormEvent) {
    ev.preventDefault();
    const next = {
      username: username.trim() ? undefined : "Enter the Student ID",
      full_name: fullName.trim() ? undefined : "Enter the full name",
      phone: phoneOk(phone) ? undefined : "Phone must have 7 to 12 digits",
    };
    setErrors(next);
    if (next.username || next.full_name || next.phone) return;
    add.mutate(
      { username: username.trim(), full_name: fullName.trim(), phone: phone.trim() },
      {
        onSuccess: (r) => {
          toast.success(
            r.created
              ? `${r.student.full_name} was created and enrolled.`
              : `${r.student.full_name} was enrolled.`,
          );
          setUsername("");
          setFullName("");
          setPhone("");
          change(false);
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={change}>
      <DialogContent>
        <form onSubmit={submit} noValidate className="flex min-h-0 flex-col">
          <DialogHeader>
            <DialogTitle>Add student</DialogTitle>
            <DialogDescription>
              The initial password is the last 4 digits of the phone number.
            </DialogDescription>
          </DialogHeader>
          <DialogBody className="space-y-4">
            <Labeled label="Student ID" error={errors.username}>
              <TextInput
                autoFocus
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </Labeled>
            <Labeled label="Full name" error={errors.full_name}>
              <TextInput
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
              />
            </Labeled>
            <Labeled label="Phone" error={errors.phone}>
              <TextInput
                inputMode="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
              />
            </Labeled>
            <ErrorMsg error={add.error} />
          </DialogBody>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => change(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={add.isPending}>
              {add.isPending ? "Adding…" : "Add student"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function EditStudentDialog({
  classId,
  s,
  open,
  onOpenChange,
}: {
  classId: string;
  s: StudentOut;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const update = useUpdateStudent(classId);
  const [name, setName] = useState(s.full_name);
  const [phone, setPhone] = useState(s.phone);
  const [errors, setErrors] = useState<{ name?: string; phone?: string }>({});

  function change(v: boolean) {
    onOpenChange(v);
    if (!v) {
      update.reset();
      setErrors({});
      setName(s.full_name);
      setPhone(s.phone);
    }
  }

  function submit(ev: React.FormEvent) {
    ev.preventDefault();
    const next = {
      name: name.trim() ? undefined : "Name is required",
      phone: phoneOk(phone) ? undefined : "Phone must have 7 to 12 digits",
    };
    setErrors(next);
    if (next.name || next.phone) return;
    update.mutate(
      { userId: s.id, body: { full_name: name.trim(), phone: phone.trim() } },
      {
        onSuccess: () => {
          toast.success("Student updated");
          onOpenChange(false);
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={change}>
      <DialogContent>
        <form onSubmit={submit} noValidate className="flex min-h-0 flex-col">
          <DialogHeader>
            <DialogTitle>Edit student</DialogTitle>
            <DialogDescription>Student ID {s.username}</DialogDescription>
          </DialogHeader>
          <DialogBody className="space-y-4">
            <Labeled label="Full name" error={errors.name}>
              <TextInput value={name} onChange={(e) => setName(e.target.value)} />
            </Labeled>
            <Labeled label="Phone" error={errors.phone}>
              <TextInput
                inputMode="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
              />
            </Labeled>
            <ErrorMsg error={update.error} />
          </DialogBody>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => change(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={update.isPending}>
              {update.isPending ? "Saving…" : "Save changes"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function StudentActions({ classId, s }: { classId: string; s: StudentOut }) {
  const update = useUpdateStudent(classId);
  const reset = useResetStudentPassword(classId);
  const [editOpen, setEditOpen] = useState(false);
  const [resetOpen, setResetOpen] = useState(false);

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger
          aria-label={`Actions for ${s.full_name}`}
          render={
            <Button variant="ghost" size="icon-sm">
              <MoreHorizontal />
            </Button>
          }
        />
        <DropdownMenuContent>
          <DropdownMenuItem onClick={() => setEditOpen(true)}>
            <Pencil /> Edit details
          </DropdownMenuItem>
          <DropdownMenuItem
            disabled={update.isPending}
            onClick={() =>
              update.mutate(
                { userId: s.id, body: { is_active: !s.is_active } },
                {
                  onSuccess: () =>
                    toast.success(
                      s.is_active
                        ? `${s.full_name} deactivated`
                        : `${s.full_name} activated`,
                    ),
                  onError: (e) => toast.error(e.message),
                },
              )
            }
          >
            <Power /> {s.is_active ? "Deactivate" : "Activate"}
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => setResetOpen(true)}>
            <KeyRound /> Reset password
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <EditStudentDialog
        classId={classId}
        s={s}
        open={editOpen}
        onOpenChange={setEditOpen}
      />
      <ConfirmDialog
        open={resetOpen}
        onOpenChange={(v) => {
          setResetOpen(v);
          if (!v) reset.reset();
        }}
        title="Reset password"
        description={
          <>
            Reset {s.full_name}&apos;s password to the last 4 digits of their phone?
            The student must change it at next login.
            {reset.error && (
              <span role="alert" className="mt-2 block text-fin-danger">
                {reset.error.message}
              </span>
            )}
          </>
        }
        confirmLabel="Reset password"
        pending={reset.isPending}
        onConfirm={() =>
          reset.mutate(s.id, {
            onSuccess: () => {
              toast.success(`Password reset for ${s.full_name}`);
              setResetOpen(false);
            },
          })
        }
      />
    </>
  );
}

export function StudentsTab({ classId }: { classId: string }) {
  const students = useStudents(classId);
  const [addOpen, setAddOpen] = useState(false);

  const columns: ColumnDef<StudentOut>[] = [
    {
      accessorKey: "username",
      header: "Student ID",
      cell: ({ getValue }) => (
        <span className="font-mono text-xs text-text-muted">
          {getValue<string>()}
        </span>
      ),
    },
    {
      accessorKey: "full_name",
      header: "Name",
      cell: ({ getValue }) => (
        <span className="font-medium text-text-strong">{getValue<string>()}</span>
      ),
    },
    { accessorKey: "phone", header: "Phone" },
    {
      id: "status",
      header: "Status",
      accessorFn: (s) => (s.is_active ? "Active" : "Inactive"),
      cell: ({ row }) => (
        <StatusBadge
          status={row.original.is_active ? "active" : "inactive"}
          label={row.original.is_active ? "Active" : "Inactive"}
        />
      ),
    },
    {
      id: "actions",
      header: () => <span className="sr-only">Actions</span>,
      enableSorting: false,
      enableHiding: false,
      meta: { className: "w-12 text-right" },
      cell: ({ row }) => <StudentActions classId={classId} s={row.original} />,
    },
  ];

  const addButton = (
    <Button onClick={() => setAddOpen(true)}>
      <Plus /> Add student
    </Button>
  );

  return (
    <>
      <DataTable
        columns={columns}
        data={students.data}
        isLoading={students.isPending}
        error={students.error}
        getRowId={(s) => s.id}
        searchPlaceholder="Search by ID, name or phone…"
        initialSort={[{ id: "full_name", desc: false }]}
        toolbar={
          <>
            <Link href={`/instructor/classes/${classId}/import`}>
              <Button variant="outline" size="sm">
                <Upload /> Import CSV
              </Button>
            </Link>
            <Button size="sm" onClick={() => setAddOpen(true)}>
              <Plus /> Add student
            </Button>
          </>
        }
        emptyTitle="No students yet"
        emptyDescription="Add a student manually or import a CSV file."
        emptyAction={
          <div className="flex gap-2">
            {addButton}
            <Link href={`/instructor/classes/${classId}/import`}>
              <Button variant="outline">
                <Upload /> Import CSV
              </Button>
            </Link>
          </div>
        }
      />
      <AddStudentDialog classId={classId} open={addOpen} onOpenChange={setAddOpen} />
    </>
  );
}
