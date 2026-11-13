"use client";

import { useState } from "react";
import { toast } from "sonner";
import type { ColumnDef } from "@tanstack/react-table";
import { KeyRound, Plus, Power } from "lucide-react";
import {
  useCreateInstructor,
  useInstructors,
  useResetInstructorPassword,
  useSetInstructorActive,
} from "@/lib/admin";
import type { InstructorOut } from "@/lib/api/types";
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
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { DataTable } from "@/components/shared/data-table";
import { PageHeader } from "@/components/shared/page-header";
import { StatusBadge } from "@/components/shared/status-badge";
import { ErrorMsg, Labeled, TextInput, errorText } from "@/components/lab/common";

function CreateDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const create = useCreateInstructor();
  const [username, setUsername] = useState("");
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [errors, setErrors] = useState<{ username?: string; name?: string; phone?: string }>({});

  function change(o: boolean) {
    if (!o) {
      setUsername("");
      setFullName("");
      setPhone("");
      setErrors({});
      create.reset();
    }
    onOpenChange(o);
  }

  function submit(ev: React.FormEvent) {
    ev.preventDefault();
    const e = {
      username: username.trim() ? undefined : "Enter a username",
      name: fullName.trim() ? undefined : "Enter the full name",
      phone:
        phone.replace(/\D/g, "").length >= 4
          ? undefined
          : "Enter a phone number with at least 4 digits",
    };
    setErrors(e);
    if (e.username || e.name || e.phone) return;
    create.mutate(
      { username: username.trim(), full_name: fullName.trim(), phone: phone.trim() },
      {
        onSuccess: (u) => {
          toast.success(`Instructor ${u.username} created`);
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
            <DialogTitle>New instructor</DialogTitle>
            <DialogDescription>
              The first password is the last 4 digits of the phone number. The instructor
              must change it at first sign-in.
            </DialogDescription>
          </DialogHeader>
          <DialogBody className="space-y-4">
            <Labeled label="Username" required error={errors.username}>
              <TextInput autoFocus value={username} onChange={(e) => setUsername(e.target.value)} />
            </Labeled>
            <Labeled label="Full name" required error={errors.name}>
              <TextInput value={fullName} onChange={(e) => setFullName(e.target.value)} />
            </Labeled>
            <Labeled
              label="Phone"
              required
              error={errors.phone}
              hint="The last 4 digits become the first password."
            >
              <TextInput inputMode="tel" value={phone} onChange={(e) => setPhone(e.target.value)} />
            </Labeled>
            <ErrorMsg error={create.error} />
          </DialogBody>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => change(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? "Creating…" : "Create instructor"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function InstructorsPage() {
  const list = useInstructors();
  const setActive = useSetInstructorActive();
  const reset = useResetInstructorPassword();
  const [creating, setCreating] = useState(false);
  const [toggle, setToggle] = useState<InstructorOut | null>(null);
  const [resetting, setResetting] = useState<InstructorOut | null>(null);

  const columns: ColumnDef<InstructorOut>[] = [
    { accessorKey: "username", header: "Username", meta: { label: "Username" } },
    { accessorKey: "full_name", header: "Name", meta: { label: "Name" } },
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
        <div className="flex justify-end gap-2">
          <Button size="sm" variant="outline" onClick={() => setResetting(row.original)}>
            <KeyRound /> Reset password
          </Button>
          <Button size="sm" variant="outline" onClick={() => setToggle(row.original)}>
            <Power /> {row.original.is_active ? "Deactivate" : "Activate"}
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="mx-auto w-full max-w-5xl">
      <PageHeader
        title="Instructors"
        subtitle="Create instructor accounts, deactivate them or reset a forgotten password."
        actions={
          <Button onClick={() => setCreating(true)}>
            <Plus /> New instructor
          </Button>
        }
      />
      <DataTable
        columns={columns}
        data={list.data}
        isLoading={list.isPending}
        error={list.error}
        getRowId={(r) => r.id}
        searchPlaceholder="Search instructors…"
        emptyTitle="No instructors yet"
        emptyDescription="Create the first instructor account."
        columnToggle={false}
        fit
      />
      <CreateDialog open={creating} onOpenChange={setCreating} />
      <ConfirmDialog
        open={!!toggle}
        onOpenChange={(o) => !o && setToggle(null)}
        title={toggle?.is_active ? "Deactivate instructor?" : "Activate instructor?"}
        description={
          toggle?.is_active
            ? `${toggle?.full_name} will no longer be able to sign in.`
            : `${toggle?.full_name} will be able to sign in again.`
        }
        confirmLabel={toggle?.is_active ? "Deactivate" : "Activate"}
        destructive={toggle?.is_active}
        pending={setActive.isPending}
        onConfirm={() =>
          toggle &&
          setActive.mutate(
            { id: toggle.id, is_active: !toggle.is_active },
            {
              onSuccess: (u) => {
                toast.success(`${u.username} is now ${u.is_active ? "active" : "inactive"}`);
                setToggle(null);
              },
              onError: (e) => {
                toast.error(errorText(e));
                setToggle(null);
              },
            },
          )
        }
      />
      <ConfirmDialog
        open={!!resetting}
        onOpenChange={(o) => !o && setResetting(null)}
        title="Reset password?"
        description={`The password of ${resetting?.full_name} is reset to the last 4 digits of their phone number. They must change it at next sign-in.`}
        confirmLabel="Reset password"
        pending={reset.isPending}
        onConfirm={() =>
          resetting &&
          reset.mutate(resetting.id, {
            onSuccess: () => {
              toast.success(`Password reset for ${resetting.username}`);
              setResetting(null);
            },
            onError: (e) => {
              toast.error(errorText(e));
              setResetting(null);
            },
          })
        }
      />
    </div>
  );
}
