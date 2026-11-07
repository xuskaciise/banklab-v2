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
import { ErrorMsg, Labeled, TextInput } from "./common";

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
  const [errors, setErrors] = useState<{ name?: string; code?: string }>({});

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
    };
    setErrors(next);
    if (next.name || next.code) return;
    create.mutate(
      { name: name.trim(), code: code.trim() },
      {
        onSuccess: (c) => {
          toast.success(`Class "${c.name}" created`);
          setName("");
          setCode("");
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
