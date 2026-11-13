"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import type { ColumnDef } from "@tanstack/react-table";
import { Plus } from "lucide-react";
import { useCoaTemplates, useCreateCoaTemplate } from "@/lib/admin";
import type { CoaTemplateRow } from "@/lib/api/types";
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
import { DataTable } from "@/components/shared/data-table";
import { PageHeader } from "@/components/shared/page-header";
import { StatusBadge } from "@/components/shared/status-badge";
import { ErrorMsg, Labeled, Select, TextInput } from "@/components/lab/common";

function CreateDialog({
  open,
  onOpenChange,
  templates,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  templates: CoaTemplateRow[];
}) {
  const router = useRouter();
  const create = useCreateCoaTemplate();
  const [name, setName] = useState("");
  const [copyFrom, setCopyFrom] = useState("");
  const [error, setError] = useState<string>();

  function change(o: boolean) {
    if (!o) {
      setName("");
      setCopyFrom("");
      setError(undefined);
      create.reset();
    }
    onOpenChange(o);
  }

  function submit(ev: React.FormEvent) {
    ev.preventDefault();
    if (!name.trim()) return setError("Enter a template name");
    setError(undefined);
    create.mutate(
      { name: name.trim(), copy_from_id: copyFrom || null },
      {
        onSuccess: (t) => {
          toast.success(`Template "${t.name}" created`);
          change(false);
          router.push(`/admin/coa-templates/${t.id}`);
        },
      },
    );
  }

  const def = templates.find((t) => t.is_default);
  return (
    <Dialog open={open} onOpenChange={change}>
      <DialogContent>
        <form onSubmit={submit} noValidate className="flex min-h-0 flex-col">
          <DialogHeader>
            <DialogTitle>New CoA template</DialogTitle>
            <DialogDescription>
              Start from the default chart of accounts or copy another template, then adjust the lines.
            </DialogDescription>
          </DialogHeader>
          <DialogBody className="space-y-4">
            <Labeled label="Name" required error={error}>
              <TextInput autoFocus value={name} onChange={(e) => setName(e.target.value)} />
            </Labeled>
            <Labeled label="Copy lines from" hint="Leave on the default to start from the standard chart.">
              <Select className="w-full" value={copyFrom} onChange={(e) => setCopyFrom(e.target.value)}>
                <option value="">{def ? `${def.name} (default)` : "Default chart of accounts"}</option>
                {templates
                  .filter((t) => !t.is_default)
                  .map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name}
                    </option>
                  ))}
              </Select>
            </Labeled>
            <ErrorMsg error={create.error} />
          </DialogBody>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => change(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? "Creating…" : "Create template"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function CoaTemplatesPage() {
  const list = useCoaTemplates();
  const [creating, setCreating] = useState(false);

  const columns: ColumnDef<CoaTemplateRow>[] = [
    {
      accessorKey: "name",
      header: "Name",
      meta: { label: "Name" },
      cell: ({ row }) => (
        <Link
          href={`/admin/coa-templates/${row.original.id}`}
          className="font-medium text-bank-accent hover:underline"
        >
          {row.original.name}
        </Link>
      ),
    },
    {
      accessorKey: "is_default",
      header: "Type",
      meta: { label: "Type" },
      cell: ({ row }) =>
        row.original.is_default ? (
          <StatusBadge status="active" label="Default" tone="info" />
        ) : (
          <span className="text-text-muted">Custom</span>
        ),
    },
    {
      accessorKey: "line_count",
      header: "Lines",
      meta: { label: "Lines", className: "text-right" },
      cell: ({ row }) => <span className="tabular-nums">{row.original.line_count}</span>,
    },
    {
      accessorKey: "session_template_count",
      header: "Session templates",
      meta: { label: "Session templates", className: "text-right" },
      cell: ({ row }) => <span className="tabular-nums">{row.original.session_template_count}</span>,
    },
  ];

  return (
    <div className="mx-auto w-full max-w-5xl">
      <PageHeader
        title="CoA templates"
        subtitle="Charts of accounts that sessions are created from."
        actions={
          <Button onClick={() => setCreating(true)} disabled={!list.data}>
            <Plus /> New template
          </Button>
        }
      />
      <DataTable
        columns={columns}
        data={list.data}
        isLoading={list.isPending}
        error={list.error}
        getRowId={(r) => r.id}
        searchPlaceholder="Search templates…"
        emptyTitle="No CoA templates"
        columnToggle={false}
        fit
      />
      <CreateDialog open={creating} onOpenChange={setCreating} templates={list.data ?? []} />
    </div>
  );
}
