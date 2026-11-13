"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import { useCreateClass } from "@/lib/lab";
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
import { useMe } from "@/lib/auth";
import { useInstructors } from "@/lib/admin";
import { ErrorMsg, Labeled, Select, TextInput } from "./common";

/** "New class" button + dialog with client validation and server errors. */
export function CreateClassDialog({
  variant = "default",
  label = "New class",
}: {
  variant?: "default" | "outline";
  label?: string;
}) {
  const create = useCreateClass();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [instructorId, setInstructorId] = useState("");
  const [errors, setErrors] = useState<{
    name?: string;
    code?: string;
    instructor?: string;
  }>({});
  const { data: me } = useMe();
  const isAdmin = me?.platform_role === "admin";
  const instructors = useInstructors(isAdmin);
  const activeInstructors = (instructors.data ?? []).filter((i) => i.is_active);

  function onOpenChange(v: boolean) {
    setOpen(v);
    if (!v) {
      create.reset();
      setErrors({});
    }
  }

  function submit(ev: React.FormEvent) {
    ev.preventDefault();
    const next = {
      name: name.trim() ? undefined : "Enter a class name",
      code: code.trim() ? undefined : "Enter a class code",
      instructor: isAdmin && !instructorId ? "Select an instructor" : undefined,
    };
    setErrors(next);
    if (next.name || next.code || next.instructor) return;
    create.mutate(
      {
        name: name.trim(),
        code: code.trim(),
        ...(isAdmin ? { instructor_id: instructorId } : {}),
      },
      {
        onSuccess: (c) => {
          toast.success(`Class "${c.name}" created`);
          setName("");
          setCode("");
          setInstructorId("");
          onOpenChange(false);
        },
      },
    );
  }

  return (
    <>
      <Button variant={variant} onClick={() => setOpen(true)}>
        <Plus /> {label}
      </Button>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent>
          <form onSubmit={submit} noValidate className="flex min-h-0 flex-col">
            <DialogHeader>
              <DialogTitle>New class</DialogTitle>
              <DialogDescription>
                Create a class, then enrol students and open sessions for it.
              </DialogDescription>
            </DialogHeader>
            <DialogBody className="space-y-4">
              <Labeled label="Class name" error={errors.name}>
                <TextInput
                  autoFocus
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </Labeled>
              <Labeled label="Code" error={errors.code} hint="For example BNK-101">
                <TextInput value={code} onChange={(e) => setCode(e.target.value)} />
              </Labeled>
              {isAdmin && (
                <Labeled label="Instructor" error={errors.instructor} required>
                  <Select
                    className="w-full"
                    value={instructorId}
                    onChange={(e) => setInstructorId(e.target.value)}
                  >
                    <option value="">
                      {instructors.isLoading ? "Loading…" : "Select instructor"}
                    </option>
                    {activeInstructors.map((i) => (
                      <option key={i.id} value={i.id}>
                        {i.full_name}
                      </option>
                    ))}
                  </Select>
                </Labeled>
              )}
              <ErrorMsg error={create.error} />
            </DialogBody>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={create.isPending}>
                {create.isPending ? "Creating…" : "Create class"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
