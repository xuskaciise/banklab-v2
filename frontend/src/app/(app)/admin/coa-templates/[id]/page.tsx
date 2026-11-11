"use client";

import { use, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { ArrowLeft, Check, Lock, Pencil, Plus, Trash2, X } from "lucide-react";
import {
  useAddCoaLine,
  useCoaTemplate,
  useDeleteCoaTemplate,
  useUpdateCoaLine,
} from "@/lib/admin";
import type { CoaLineOut } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { FormGrid, FormSection } from "@/components/shared/form-layout";
import { PageHeader } from "@/components/shared/page-header";
import { StatusBadge } from "@/components/shared/status-badge";
import {
  ErrorMsg,
  Labeled,
  Loading,
  Select,
  Table,
  Td,
  TextInput,
  Th,
  errorText,
} from "@/components/lab/common";

const TYPES = ["asset", "liability", "equity", "income", "expense"];

function LineRow({ templateId, line }: { templateId: string; line: CoaLineOut }) {
  const update = useUpdateCoaLine(templateId);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(line.name);
  const locked = !!line.system_tag;

  function save() {
    if (!name.trim()) return toast.error("Enter a name");
    update.mutate(
      { lineId: line.id, patch: { name: name.trim() } },
      {
        onSuccess: () => {
          toast.success(`Line ${line.code} renamed`);
          setEditing(false);
        },
        onError: (e) => toast.error(errorText(e)),
      },
    );
  }
  function toggleActive() {
    update.mutate(
      { lineId: line.id, patch: { is_active: !line.is_active } },
      { onError: (e) => toast.error(errorText(e)) },
    );
  }

  return (
    <tr>
      <Td className="font-mono text-xs tabular-nums">{line.code}</Td>
      <Td>
        {editing ? (
          <TextInput
            autoFocus
            value={name}
            aria-label={`Name of ${line.code}`}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") save();
              if (e.key === "Escape") setEditing(false);
            }}
          />
        ) : (
          <span className="inline-flex items-center gap-2">
            {line.name}
            {locked && (
              <span title={`System account (${line.system_tag}): locked`}>
                <Lock className="size-3.5 text-text-muted" aria-label="Locked system account" />
              </span>
            )}
          </span>
        )}
      </Td>
      <Td className="capitalize">{line.type}</Td>
      <Td className="font-mono text-xs">{line.parent_code || "—"}</Td>
      <Td>{line.postable ? "Yes" : "No"}</Td>
      <Td>
        <StatusBadge
          status={line.is_active ? "active" : "inactive"}
          label={line.is_active ? "Active" : "Inactive"}
        />
      </Td>
      <Td className="text-right">
        {locked ? null : editing ? (
          <div className="flex justify-end gap-1">
            <Button size="sm" onClick={save} disabled={update.isPending} aria-label="Save name">
              <Check />
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setName(line.name);
                setEditing(false);
              }}
              aria-label="Cancel"
            >
              <X />
            </Button>
          </div>
        ) : (
          <div className="flex justify-end gap-1">
            <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
              <Pencil /> Rename
            </Button>
            <Button size="sm" variant="outline" onClick={toggleActive} disabled={update.isPending}>
              {line.is_active ? "Deactivate" : "Activate"}
            </Button>
          </div>
        )}
      </Td>
    </tr>
  );
}

function AddLineForm({ templateId, codes }: { templateId: string; codes: string[] }) {
  const add = useAddCoaLine(templateId);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [type, setType] = useState("asset");
  const [parent, setParent] = useState("");
  const [postable, setPostable] = useState(true);
  const [errors, setErrors] = useState<{ code?: string; name?: string }>({});

  function submit(ev: React.FormEvent) {
    ev.preventDefault();
    const e = {
      code: code.trim() ? undefined : "Enter a code",
      name: name.trim() ? undefined : "Enter a name",
    };
    setErrors(e);
    if (e.code || e.name) return;
    add.mutate(
      { code: code.trim(), name: name.trim(), type, parent_code: parent, postable },
      {
        onSuccess: (l) => {
          toast.success(`Line ${l.code} added`);
          setCode("");
          setName("");
          setParent("");
        },
      },
    );
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-4">
      <FormGrid cols={3}>
        <Labeled label="Code" required error={errors.code}>
          <TextInput value={code} onChange={(e) => setCode(e.target.value)} />
        </Labeled>
        <Labeled label="Name" required error={errors.name}>
          <TextInput value={name} onChange={(e) => setName(e.target.value)} />
        </Labeled>
        <Labeled label="Type" required>
          <Select className="w-full capitalize" value={type} onChange={(e) => setType(e.target.value)}>
            {TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </Select>
        </Labeled>
        <Labeled label="Parent" optional hint="Must have the same type.">
          <Select className="w-full" value={parent} onChange={(e) => setParent(e.target.value)}>
            <option value="">No parent</option>
            {codes.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </Select>
        </Labeled>
        <label className="flex items-center gap-2 self-end pb-2 text-sm text-text-strong">
          <input
            type="checkbox"
            checked={postable}
            onChange={(e) => setPostable(e.target.checked)}
            className="size-4 accent-bank-primary"
          />
          Postable (accepts journal lines)
        </label>
      </FormGrid>
      <ErrorMsg error={add.error} />
      <Button type="submit" disabled={add.isPending}>
        <Plus /> {add.isPending ? "Adding…" : "Add line"}
      </Button>
    </form>
  );
}

export default function CoaTemplateDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const q = useCoaTemplate(id);
  const del = useDeleteCoaTemplate();
  const [confirming, setConfirming] = useState(false);

  if (q.isPending) return <Loading label="Loading template" />;
  if (q.isError) return <ErrorMsg error={q.error} />;
  const t = q.data;

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6">
      <Link
        href="/admin/coa-templates"
        className="inline-flex items-center gap-1 text-sm text-bank-accent hover:underline"
      >
        <ArrowLeft className="size-4" aria-hidden /> CoA templates
      </Link>
      <PageHeader
        className="mb-0"
        title={
          <span className="inline-flex flex-wrap items-center gap-3">
            {t.name}
            {t.is_default && <StatusBadge status="active" label="Default" tone="info" />}
          </span>
        }
        subtitle={`${t.lines.length} lines. Lines with a lock are system accounts and cannot be changed.`}
        actions={
          t.is_default ? undefined : (
            <Button variant="destructive" onClick={() => setConfirming(true)}>
              <Trash2 /> Delete template
            </Button>
          )
        }
      />
      <FormSection title="Add line">
        <AddLineForm
          templateId={id}
          codes={t.lines.map((l) => l.code)}
        />
      </FormSection>
      <Table>
        <thead>
          <tr>
            <Th>Code</Th>
            <Th>Name</Th>
            <Th>Type</Th>
            <Th>Parent</Th>
            <Th>Postable</Th>
            <Th>Status</Th>
            <Th className="text-right">Actions</Th>
          </tr>
        </thead>
        <tbody>
          {t.lines.map((l) => (
            <LineRow key={`${l.id}:${l.name}:${l.is_active}`} templateId={id} line={l} />
          ))}
        </tbody>
      </Table>
      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title="Delete template?"
        description={`"${t.name}" and its lines will be deleted. This cannot be undone.`}
        confirmLabel="Delete"
        destructive
        pending={del.isPending}
        onConfirm={() =>
          del.mutate(id, {
            onSuccess: () => {
              toast.success("Template deleted");
              router.replace("/admin/coa-templates");
            },
            onError: (e) => {
              toast.error(errorText(e));
              setConfirming(false);
            },
          })
        }
      />
    </div>
  );
}
