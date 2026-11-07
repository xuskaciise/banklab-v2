"use client";

import { useState } from "react";
import Link from "next/link";
import { useClasses, useCreateClass } from "@/lib/lab";
import { Button } from "@/components/ui/button";
import {
  Empty,
  ErrorMsg,
  Labeled,
  PageHeader,
  QueryState,
  Table,
  Td,
  TextInput,
  Th,
} from "@/components/lab/common";

export default function ClassesPage() {
  const classes = useClasses();
  const create = useCreateClass();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [errors, setErrors] = useState<{ name?: string; code?: string }>({});

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
        onSuccess: () => {
          setName("");
          setCode("");
          setOpen(false);
        },
      },
    );
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="Classes"
        actions={
          <Button onClick={() => setOpen((v) => !v)}>
            {open ? "Cancel" : "New class"}
          </Button>
        }
      />
      {open && (
        <form
          onSubmit={submit}
          noValidate
          className="grid max-w-xl gap-4 rounded-lg border border-border bg-card p-4"
        >
          <Labeled label="Class name" error={errors.name}>
            <TextInput value={name} onChange={(e) => setName(e.target.value)} />
          </Labeled>
          <Labeled label="Code" error={errors.code} hint="For example BNK-101">
            <TextInput value={code} onChange={(e) => setCode(e.target.value)} />
          </Labeled>
          <ErrorMsg error={create.error} />
          <div>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? "Creating…" : "Create class"}
            </Button>
          </div>
        </form>
      )}
      <QueryState query={classes}>
        {classes.data?.length ? (
          <Table>
            <thead>
              <tr>
                <Th>Name</Th>
                <Th>Code</Th>
                <Th>Instructor</Th>
                <Th />
              </tr>
            </thead>
            <tbody>
              {classes.data.map((c) => (
                <tr key={c.id} className="hover:bg-hover">
                  <Td className="font-medium text-text-strong">{c.name}</Td>
                  <Td>{c.code}</Td>
                  <Td>{c.instructor_name}</Td>
                  <Td className="text-right">
                    <Link
                      href={`/instructor/classes/${c.id}`}
                      className="text-bank-accent hover:underline"
                    >
                      Open
                    </Link>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        ) : (
          <Empty>No classes yet. Create one to get started.</Empty>
        )}
      </QueryState>
    </div>
  );
}
