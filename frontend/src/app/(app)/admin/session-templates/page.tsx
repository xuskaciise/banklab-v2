"use client";

import { useState } from "react";
import { toast } from "sonner";
import type { ColumnDef } from "@tanstack/react-table";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { BANK_ROLES } from "@/lib/lab";
import {
  useAdminSessionTemplates,
  useCoaTemplates,
  useDeleteSessionTemplate,
  useSaveSessionTemplate,
} from "@/lib/admin";
import { useSosEnabled } from "@/lib/platform";
import type { CoaTemplateRow, SessionTemplateOut } from "@/lib/api/types";
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
import { RolesField, SwitchRow } from "@/components/lab/roles-field";
import { KIND_OPTS, STRUCTURE_OPTS, VIS_OPTS } from "@/components/lab/session-options";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { DataTable } from "@/components/shared/data-table";
import { FormGrid, OptionCards } from "@/components/shared/form-layout";
import { PageHeader } from "@/components/shared/page-header";
import { ErrorMsg, Labeled, Select, TextInput, errorText } from "@/components/lab/common";

const amount = (v: string) =>
  /^\d{1,16}(\.\d{1,2})?$/.test(v.trim()) && Number(v) > 0
    ? undefined
    : "Enter a positive amount with at most 2 decimals";

function TemplateForm({
  open,
  onOpenChange,
  editing,
  coas,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  editing: SessionTemplateOut | null;
  coas: CoaTemplateRow[];
}) {
  const save = useSaveSessionTemplate();
  const sosOn = useSosEnabled();
  const t = editing;
  const [name, setName] = useState(t?.name ?? "");
  const [kind, setKind] = useState<"practice" | "exam">(t?.kind === "exam" ? "exam" : "practice");
  const [structure, setStructure] = useState(t?.structure ?? "single_bank");
  const [roles, setRoles] = useState<string[]>(t?.allowed_roles ?? [...BANK_ROLES]);
  const [visibility, setVisibility] = useState(t?.default_visibility ?? "all");
  const [panel, setPanel] = useState(t?.learning_panel ?? true);
  const [capUsd, setCapUsd] = useState(String(t?.opening_capital_usd ?? "1000000.00"));
  const [capSos, setCapSos] = useState(String(t?.opening_capital_sos ?? "5000000000.00"));
  const [coaId, setCoaId] = useState(t?.coa_template_id ?? "");
  const [errors, setErrors] = useState<{
    name?: string;
    roles?: string;
    capUsd?: string;
    capSos?: string;
  }>({});

  const exam = kind === "exam";

  function submit(ev: React.FormEvent) {
    ev.preventDefault();
    const e = {
      name: name.trim() ? undefined : "Enter a template name",
      roles: roles.length ? undefined : "Select at least one role",
      capUsd: amount(capUsd),
      capSos: sosOn ? amount(capSos) : undefined,
    };
    setErrors(e);
    if (e.name || e.roles || e.capUsd || e.capSos) return;
    save.mutate(
      {
        id: t?.id,
        body: {
          name: name.trim(),
          kind,
          structure: exam ? "single_bank" : structure,
          allowed_roles: roles,
          default_visibility: exam ? "own" : visibility,
          learning_panel: exam ? false : panel,
          seed_profile: t?.seed_profile ?? "",
          opening_capital_usd: capUsd.trim(),
          opening_capital_sos: capSos.trim(),
          coa_template_id: coaId || null,
        },
      },
      {
        onSuccess: (r) => {
          toast.success(`Template "${r.name}" saved`);
          onOpenChange(false);
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <form onSubmit={submit} noValidate className="flex min-h-0 flex-col">
          <DialogHeader>
            <DialogTitle>{t ? "Edit session template" : "New session template"}</DialogTitle>
            <DialogDescription>
              Institution-wide template that instructors can pick when opening a session.
            </DialogDescription>
          </DialogHeader>
          <DialogBody className="space-y-4">
            <Labeled label="Template name" required error={errors.name}>
              <TextInput autoFocus value={name} onChange={(e) => setName(e.target.value)} />
            </Labeled>
            <Labeled label="Chart of accounts" hint="Used for the bank books of sessions made from this template.">
              <Select className="w-full" value={coaId} onChange={(e) => setCoaId(e.target.value)}>
                <option value="">Default chart of accounts</option>
                {coas.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                    {c.is_default ? " (default)" : ""}
                  </option>
                ))}
              </Select>
            </Labeled>
            <p className="text-sm font-medium text-text-strong">Kind</p>
            <OptionCards label="Kind" columns={2} options={KIND_OPTS} value={kind} onChange={setKind} />
            <p className="text-sm font-medium text-text-strong">Structure</p>
            <OptionCards
              label="Structure"
              columns={2}
              options={STRUCTURE_OPTS}
              value={(exam ? "single_bank" : structure) as "single_bank" | "per_group"}
              onChange={setStructure}
              disabled={exam}
            />
            <p className="text-sm font-medium text-text-strong">Default visibility</p>
            <OptionCards
              label="Default visibility"
              columns={2}
              options={VIS_OPTS}
              value={(exam ? "own" : visibility) as "all" | "own"}
              onChange={setVisibility}
              disabled={exam}
            />
            <FormGrid>
              <Labeled label="Opening capital (USD)" required error={errors.capUsd}>
                <TextInput inputMode="decimal" value={capUsd} onChange={(e) => setCapUsd(e.target.value)} />
              </Labeled>
              {sosOn && (
                <Labeled label="Opening capital (SOS)" required error={errors.capSos}>
                  <TextInput inputMode="decimal" value={capSos} onChange={(e) => setCapSos(e.target.value)} />
                </Labeled>
              )}
            </FormGrid>
            <RolesField
              roles={roles}
              onToggle={(r) =>
                setRoles((cur) => (cur.includes(r) ? cur.filter((x) => x !== r) : [...cur, r]))
              }
              error={errors.roles}
            />
            <SwitchRow
              title="Dr/Cr learning panel"
              description="After each posting, show students the debit and credit lines it created."
              checked={exam ? false : panel}
              disabled={exam}
              note="Turned off for exams."
              onChange={setPanel}
            />
            <ErrorMsg error={save.error} />
          </DialogBody>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={save.isPending}>
              {save.isPending ? "Saving…" : "Save template"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function SessionTemplatesPage() {
  const list = useAdminSessionTemplates();
  const coas = useCoaTemplates();
  const del = useDeleteSessionTemplate();
  const [form, setForm] = useState<{ editing: SessionTemplateOut | null } | null>(null);
  const [deleting, setDeleting] = useState<SessionTemplateOut | null>(null);
  const coaName = (id?: string | null) =>
    id ? (coas.data?.find((c) => c.id === id)?.name ?? "—") : "Default";

  const columns: ColumnDef<SessionTemplateOut>[] = [
    { accessorKey: "name", header: "Name", meta: { label: "Name" } },
    {
      accessorKey: "kind",
      header: "Kind",
      meta: { label: "Kind" },
      cell: ({ row }) => <span className="capitalize">{row.original.kind}</span>,
    },
    {
      accessorKey: "structure",
      header: "Structure",
      meta: { label: "Structure" },
      cell: ({ row }) => (row.original.structure === "per_group" ? "One bank per group" : "Single bank"),
    },
    {
      id: "coa",
      header: "Chart of accounts",
      meta: { label: "Chart of accounts" },
      cell: ({ row }) => coaName(row.original.coa_template_id),
    },
    {
      id: "actions",
      header: "",
      enableSorting: false,
      meta: { label: "Actions", className: "text-right" },
      cell: ({ row }) => (
        <div className="flex justify-end gap-2">
          <Button size="sm" variant="outline" onClick={() => setForm({ editing: row.original })}>
            <Pencil /> Edit
          </Button>
          <Button size="sm" variant="outline" onClick={() => setDeleting(row.original)}>
            <Trash2 /> Delete
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="mx-auto w-full max-w-5xl">
      <PageHeader
        title="Session templates"
        subtitle="Institution-wide presets for opening sessions."
        actions={
          <Button onClick={() => setForm({ editing: null })} disabled={!coas.data}>
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
        emptyTitle="No session templates yet"
        emptyDescription="Create a template so instructors can open sessions quickly."
        columnToggle={false}
        fit
      />
      {form && (
        <TemplateForm
          key={form.editing?.id ?? "new"}
          open
          onOpenChange={(o) => !o && setForm(null)}
          editing={form.editing}
          coas={coas.data ?? []}
        />
      )}
      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(o) => !o && setDeleting(null)}
        title="Delete session template?"
        description={`"${deleting?.name}" will be deleted. Sessions already created from it are not affected.`}
        confirmLabel="Delete"
        destructive
        pending={del.isPending}
        onConfirm={() =>
          deleting &&
          del.mutate(deleting.id, {
            onSuccess: () => {
              toast.success("Template deleted");
              setDeleting(null);
            },
            onError: (e) => {
              toast.error(errorText(e));
              setDeleting(null);
            },
          })
        }
      />
    </div>
  );
}
