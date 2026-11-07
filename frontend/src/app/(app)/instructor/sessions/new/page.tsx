"use client";

import { Suspense, useState } from "react";
import { toast } from "sonner";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  BANK_ROLES,
  ROLE_LABEL,
  useCreateSession,
  useTemplates,
} from "@/lib/lab";
import type { TemplateOut } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import {
  ErrorMsg,
  Labeled,
  Loading,
  PageHeader,
  Select,
  TextInput,
} from "@/components/lab/common";

function Wizard({ classId }: { classId: string }) {
  const router = useRouter();
  const templates = useTemplates(classId);
  const create = useCreateSession();

  const [name, setName] = useState("");
  const [kind, setKind] = useState<"practice" | "exam">("practice");
  const [templateId, setTemplateId] = useState("");
  const [structure, setStructure] = useState("single_bank");
  const [roles, setRoles] = useState<string[]>([...BANK_ROLES]);
  const [visibility, setVisibility] = useState("all");
  const [panel, setPanel] = useState(true);
  const [errors, setErrors] = useState<{ name?: string; roles?: string }>({});

  const exam = kind === "exam";
  // Exams force a single bank, own-work visibility and no Dr/Cr panel.
  const eStructure = exam ? "single_bank" : structure;
  const eVisibility = exam ? "own" : visibility;
  const ePanel = exam ? false : panel;

  function applyTemplate(id: string) {
    setTemplateId(id);
    const t: TemplateOut | undefined = templates.data?.find((x) => x.id === id);
    if (!t) return;
    setKind(t.kind === "exam" ? "exam" : "practice");
    setStructure(t.structure);
    setRoles(t.allowed_roles);
    setVisibility(t.default_visibility);
    setPanel(t.learning_panel);
  }

  function toggleRole(r: string) {
    setRoles((cur) => (cur.includes(r) ? cur.filter((x) => x !== r) : [...cur, r]));
  }

  function submit(ev: React.FormEvent) {
    ev.preventDefault();
    const next = {
      name: name.trim() ? undefined : "Enter a session name",
      roles: roles.length ? undefined : "Select at least one role",
    };
    setErrors(next);
    if (next.name || next.roles) return;
    create.mutate(
      {
        class_id: classId,
        name: name.trim(),
        template_id: templateId || null,
        kind,
        structure: eStructure,
        allowed_roles: roles,
        default_visibility: eVisibility,
        learning_panel: ePanel,
      },
      {
        onSuccess: (s) => {
          toast.success(`Session "${s.name}" created as draft`);
          router.push(`/instructor/sessions/${s.id}`);
        },
      },
    );
  }

  return (
    <div className="max-w-2xl">
      <PageHeader
        title="Open new session"
        subtitle="The session is created as a draft. Open it from its control page once members are ready."
      />
      <form
        onSubmit={submit}
        noValidate
        className="space-y-5 rounded-xl border border-border bg-card p-6 shadow-xs"
      >
        <Labeled label="Session name" error={errors.name}>
          <TextInput value={name} onChange={(e) => setName(e.target.value)} />
        </Labeled>
        <div className="grid gap-4 sm:grid-cols-2">
          <Labeled label="Kind">
            <Select
              className="w-full"
              value={kind}
              onChange={(e) => setKind(e.target.value as "practice" | "exam")}
            >
              <option value="practice">Practice</option>
              <option value="exam">Exam</option>
            </Select>
          </Labeled>
          <Labeled label="Template (optional)">
            <Select
              className="w-full"
              value={templateId}
              onChange={(e) => applyTemplate(e.target.value)}
              disabled={templates.isPending}
            >
              <option value="">No template</option>
              {templates.data?.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </Select>
          </Labeled>
          <Labeled label="Structure">
            <Select
              className="w-full"
              value={eStructure}
              disabled={exam}
              onChange={(e) => setStructure(e.target.value)}
            >
              <option value="single_bank">Single bank</option>
              <option value="per_group">One bank per group</option>
            </Select>
          </Labeled>
          <Labeled label="Default visibility">
            <Select
              className="w-full"
              value={eVisibility}
              disabled={exam}
              onChange={(e) => setVisibility(e.target.value)}
            >
              <option value="all">Whole bank</option>
              <option value="own">Own work only</option>
            </Select>
          </Labeled>
        </div>
        {exam && (
          <p className="rounded-md bg-bank-sky-light px-3 py-2 text-sm text-bank-primary">
            Exams use a single bank, own-work visibility and no Dr/Cr learning
            panel.
          </p>
        )}
        <fieldset className="space-y-2">
          <legend className="text-sm font-medium text-text-strong">
            Allowed roles
          </legend>
          <div className="flex flex-wrap gap-4">
            {BANK_ROLES.map((r) => (
              <label key={r} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={roles.includes(r)}
                  onChange={() => toggleRole(r)}
                  className="size-4 accent-bank-primary"
                />
                {ROLE_LABEL[r]}
              </label>
            ))}
          </div>
          {errors.roles && (
            <p className="text-sm text-fin-danger">{errors.roles}</p>
          )}
        </fieldset>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={ePanel}
            disabled={exam}
            onChange={(e) => setPanel(e.target.checked)}
            className="size-4 accent-bank-primary"
          />
          Show the Dr/Cr learning panel after each posting
        </label>
        <ErrorMsg error={create.error} />
        <Button type="submit" disabled={create.isPending}>
          {create.isPending ? "Creating…" : "Create session"}
        </Button>
      </form>
    </div>
  );
}

function WizardEntry() {
  const classId = useSearchParams().get("classId");
  if (!classId)
    return (
      <p className="text-sm text-text-muted">
        Choose a class first.{" "}
        <Link href="/instructor/classes" className="text-bank-accent underline">
          Go to classes
        </Link>
      </p>
    );
  return <Wizard classId={classId} />;
}

export default function NewSessionPage() {
  return (
    <Suspense fallback={<Loading />}>
      <WizardEntry />
    </Suspense>
  );
}
