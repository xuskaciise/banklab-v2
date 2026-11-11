"use client";

import { useState } from "react";
import { UserCog } from "lucide-react";
import { toast } from "sonner";
import { useInstructors, useSetClassInstructor } from "@/lib/admin";
import type { ClassOut } from "@/lib/api/types";
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
import { ErrorMsg, Labeled, Select } from "./common";

/** Admin-only: reassign a class to another active instructor. */
export function ChangeInstructorDialog({ cls }: { cls: ClassOut }) {
  const [open, setOpen] = useState(false);
  const [instructorId, setInstructorId] = useState("");
  const [error, setError] = useState<string>();
  const instructors = useInstructors();
  const setInstructor = useSetClassInstructor(cls.id);
  const options = (instructors.data ?? []).filter(
    (i) => i.is_active && i.id !== cls.instructor_id,
  );

  function onOpenChange(v: boolean) {
    setOpen(v);
    if (!v) {
      setInstructorId("");
      setError(undefined);
      setInstructor.reset();
    }
  }

  function submit(ev: React.FormEvent) {
    ev.preventDefault();
    if (!instructorId) {
      setError("Select an instructor");
      return;
    }
    setError(undefined);
    setInstructor.mutate(instructorId, {
      onSuccess: (c) => {
        toast.success(`Class now assigned to ${c.instructor_name}`);
        onOpenChange(false);
      },
    });
  }

  return (
    <>
      <Button variant="outline" onClick={() => setOpen(true)}>
        <UserCog /> Change instructor
      </Button>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent>
          <form onSubmit={submit} noValidate className="flex min-h-0 flex-col">
            <DialogHeader>
              <DialogTitle>Change instructor</DialogTitle>
              <DialogDescription>
                {cls.name} is currently taught by {cls.instructor_name}.
              </DialogDescription>
            </DialogHeader>
            <DialogBody className="space-y-4">
              <Labeled label="New instructor" error={error} required>
                <Select
                  className="w-full"
                  value={instructorId}
                  onChange={(e) => setInstructorId(e.target.value)}
                >
                  <option value="">
                    {instructors.isLoading ? "Loading…" : "Select instructor"}
                  </option>
                  {options.map((i) => (
                    <option key={i.id} value={i.id}>
                      {i.full_name}
                    </option>
                  ))}
                </Select>
              </Labeled>
              <p className="text-sm text-muted-foreground">
                {cls.instructor_name} will lose access to this class and its
                sessions.
              </p>
              <ErrorMsg error={setInstructor.error} />
            </DialogBody>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={setInstructor.isPending}>
                {setInstructor.isPending ? "Saving…" : "Change instructor"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
