"use client";

import { Suspense, useState } from "react";
import { toast } from "sonner";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  BANK_ROLES,
  useCreateSession,
  useTemplates,
} from "@/lib/lab";
import { useSosEnabled } from "@/lib/platform";
import type { TemplateOut } from "@/lib/api/types";
import { Loader2, Plus } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { KIND_OPTS, STRUCTURE_OPTS, VIS_OPTS } from "@/components/lab/session-options";
import { RolesField, SwitchRow } from "@/components/lab/roles-field";
import {
  FormActions,
  FormGrid,
  FormPage,
  FormSection,
  OptionCards,
  SummaryCard,
} from "@/components/shared/form-layout";
import {
  ErrorMsg,
  Labeled,
  Loading,
  Select,
  TextInput,
} from "@/components/lab/common";

function Wizard({ classId }: { classId: string }) {
  const sosOn = useSosEnabled();
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
  const [capUsd, setCapUsd] = useState("1000000.00");
  const [capSos, setCapSos] = useState("5000000000.00");
  const [errors, setErrors] = useState<{
    name?: string;
    roles?: string;
    capUsd?: string;
    capSos?: string;
  }>({});

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
    setCapUsd(String(t.opening_capital_usd));
    setCapSos(String(t.opening_capital_sos));
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
    const amount = (v: string) =>
      /^\d{1,16}(\.\d{1,2})?$/.test(v.trim()) && Number(v) > 0
        ? undefined
        : "Enter a positive amount with at most 2 decimals";
    const all = { ...next, capUsd: amount(capUsd), capSos: sosOn ? amount(capSos) : undefined };
    setErrors(all);
    if (all.name || all.roles || all.capUsd || all.capSos) return;
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
        opening_capital_usd: capUsd.trim(),
        opening_capital_sos: capSos.trim(),
      },
      {
        onSuccess: (s) => {
          toast.success(`Session "${s.name}" created as draft`);
          router.push(`/instructor/sessions/${s.id}`);
        },
      },
    );
  }

  const label = (o: { value: string; label: string }[], v: string) =>
    o.find((x) => x.value === v)?.label ?? v;

  return (
    <FormPage
      title="Open new session"
      subtitle="The session is created as a draft. Open it from its control page once members are ready."
      aside={
        <div className="lg:sticky lg:top-4">
          <SummaryCard
            title="Session Summary"
            rows={[
              { label: "Name", value: name.trim() || "--" },
              { label: "Kind", value: label(KIND_OPTS, kind) },
              { label: "Structure", value: label(STRUCTURE_OPTS, eStructure) },
              { label: "Visibility", value: label(VIS_OPTS, eVisibility) },
              { label: "Roles", value: `${roles.length} allowed` },
              { label: "Capital (USD)", value: capUsd.trim() || "--" },
              ...(sosOn ? [{ label: "Capital (SOS)", value: capSos.trim() || "--" }] : []),
            ]}
          />
        </div>
      }
    >
      <form onSubmit={submit} noValidate className="space-y-6">
        <FormSection title="Session Details">
          <Labeled label="Session name" required error={errors.name}>
            <TextInput value={name} onChange={(e) => setName(e.target.value)} />
          </Labeled>
          <Labeled label="Template" optional>
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
          <p className="text-sm font-medium text-text-strong">Kind</p>
          <OptionCards
            label="Kind"
            columns={2}
            options={KIND_OPTS}
            value={kind}
            onChange={setKind}
          />
        </FormSection>
        <FormSection title="Bank Setup">
          <p className="text-sm font-medium text-text-strong">Structure</p>
          <OptionCards
            label="Structure"
            columns={2}
            options={STRUCTURE_OPTS}
            value={eStructure as "single_bank" | "per_group"}
            onChange={setStructure}
            disabled={exam}
          />
          <p className="text-sm font-medium text-text-strong">
            Default visibility
          </p>
          <OptionCards
            label="Default visibility"
            columns={2}
            options={VIS_OPTS}
            value={eVisibility as "all" | "own"}
            onChange={setVisibility}
            disabled={exam}
          />
          {exam && (
            <p className="rounded-md bg-bank-sky-light px-3 py-2 text-sm text-bank-primary">
              Exams use a single bank, own-work visibility and no Dr/Cr
              learning panel.
            </p>
          )}
          <FormGrid>
            <Labeled
              label="Opening capital (USD)"
              required
              error={errors.capUsd}
              hint="Starting capital for each bank in this session."
            >
              <TextInput
                inputMode="decimal"
                value={capUsd}
                onChange={(e) => setCapUsd(e.target.value)}
              />
            </Labeled>
            {sosOn && (
              <Labeled label="Opening capital (SOS)" required error={errors.capSos}>
                <TextInput
                  inputMode="decimal"
                  value={capSos}
                  onChange={(e) => setCapSos(e.target.value)}
                />
              </Labeled>
            )}
          </FormGrid>
        </FormSection>
        <FormSection title="Roles and Learning">
          <RolesField roles={roles} onToggle={toggleRole} error={errors.roles} />
          <SwitchRow
            title="Dr/Cr learning panel"
            description="After each posting, show students the debit and credit lines it created."
            checked={ePanel}
            disabled={exam}
            note="Turned off for exams."
            onChange={setPanel}
          />
        </FormSection>
        <ErrorMsg error={create.error} />
        <FormActions>
          <Link href="/instructor/classes" className={buttonVariants({ variant: "outline" })}>
            Cancel
          </Link>
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Plus className="size-4" aria-hidden />
            )}
            {create.isPending ? "Creating…" : "Create session"}
          </Button>
        </FormActions>
      </form>
    </FormPage>
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
