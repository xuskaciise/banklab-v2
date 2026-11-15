"use client";

import { useState } from "react";
import Link from "next/link";
import { Loader2, Lock } from "lucide-react";
import { BANK_ROLES, useTemplates } from "@/lib/lab";
import { useSosEnabled } from "@/lib/platform";
import type { SessionOut, TemplateOut } from "@/lib/api/types";
import { cn } from "@/lib/utils";
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
import { ErrorMsg, Labeled, Select, TextInput } from "@/components/lab/common";

export type SessionFormValues = {
  name: string;
  kind: "practice" | "exam";
  structure: string;
  roles: string[];
  visibility: string;
  panel: boolean;
  capUsd: string;
  capSos: string;
  seedProfile: string;
};

type TplKey = Exclude<keyof SessionFormValues, "name">;

/** Same defaults as the server uses when a field is omitted. */
export const BASE_VALUES: SessionFormValues = {
  name: "",
  kind: "practice",
  structure: "single_bank",
  roles: [...BANK_ROLES],
  visibility: "own",
  panel: true,
  capUsd: "1000000.00",
  capSos: "5000000000.00",
  seedProfile: "",
};

const TPL_KEYS: TplKey[] = [
  "kind",
  "structure",
  "roles",
  "visibility",
  "panel",
  "capUsd",
  "capSos",
  "seedProfile",
];

/** Form field -> field name used by the API's `locked_fields`. */
const LOCK_KEY: Record<TplKey | "name" | "template", string> = {
  name: "name",
  template: "template_id",
  kind: "kind",
  structure: "structure",
  roles: "allowed_roles",
  visibility: "default_visibility",
  panel: "learning_panel",
  capUsd: "opening_capital_usd",
  capSos: "opening_capital_sos",
  seedProfile: "seed_profile",
};

const EXAM_REASON =
  "Exams always use one bank, own-work visibility and no learning panel";

const money2 = (v: number | string) => {
  const n = Number(v);
  return Number.isFinite(n) ? n.toFixed(2) : String(v);
};

/** Form values for an existing session. */
export function valuesFromSession(s: SessionOut): SessionFormValues {
  return {
    name: s.name,
    kind: s.kind === "exam" ? "exam" : "practice",
    structure: s.structure,
    roles: s.allowed_roles,
    visibility: s.default_visibility,
    panel: s.learning_panel,
    capUsd: money2(s.opening_capital_usd),
    capSos: money2(s.opening_capital_sos),
    seedProfile: s.seed_profile ?? "",
  };
}

function templateValues(t: TemplateOut): Record<TplKey, SessionFormValues[TplKey]> {
  return {
    kind: t.kind === "exam" ? "exam" : "practice",
    structure: t.structure,
    roles: t.allowed_roles,
    visibility: t.default_visibility,
    panel: t.learning_panel,
    capUsd: money2(t.opening_capital_usd),
    capSos: money2(t.opening_capital_sos),
    seedProfile: t.seed_profile ?? "",
  };
}

function same(k: TplKey, a: unknown, b: unknown) {
  if (k === "roles")
    return [...(a as string[])].sort().join() === [...(b as string[])].sort().join();
  if (k === "capUsd" || k === "capSos") return Number(a) === Number(b);
  return a === b;
}

/** Values with the exam rules applied (what is actually sent to the API). */
export function effectiveValues(v: SessionFormValues): SessionFormValues {
  return v.kind === "exam"
    ? { ...v, structure: "single_bank", visibility: "own", panel: false }
    : v;
}

function Tag({ tone, children }: { tone: "tpl" | "changed"; children: React.ReactNode }) {
  return (
    <span
      className={cn(
        "rounded-full px-2 py-0.5 text-xs font-medium",
        tone === "tpl"
          ? "bg-bank-sky-light text-bank-primary"
          : "bg-fin-pending-bg text-fin-pending",
      )}
    >
      {children}
    </span>
  );
}

function LockNote({ reason }: { reason: string }) {
  return (
    <p className="flex items-start gap-1.5 text-xs text-text-muted">
      <Lock className="mt-0.5 size-3.5 shrink-0" aria-hidden />
      <span>{reason}</span>
    </p>
  );
}

export function SessionForm({
  classId,
  initial,
  initialTemplateId = "",
  locked = {},
  archived = false,
  title,
  subtitle,
  submitLabel,
  pendingLabel,
  submitIcon,
  pending,
  error,
  cancelHref,
  onSubmit,
}: {
  classId: string;
  initial: SessionFormValues;
  initialTemplateId?: string;
  locked?: Record<string, string>;
  archived?: boolean;
  title: string;
  subtitle: string;
  submitLabel: string;
  pendingLabel: string;
  submitIcon: React.ReactNode;
  pending: boolean;
  error: unknown;
  cancelHref: string;
  onSubmit: (values: SessionFormValues, templateId: string) => void;
}) {
  const sosOn = useSosEnabled();
  const templates = useTemplates(classId);
  const [v, setV] = useState<SessionFormValues>(initial);
  const [templateId, setTemplateId] = useState(initialTemplateId);
  const [errors, setErrors] = useState<{
    name?: string;
    roles?: string;
    capUsd?: string;
    capSos?: string;
    seedProfile?: string;
  }>({});

  const set = <K extends keyof SessionFormValues>(k: K, val: SessionFormValues[K]) =>
    setV((cur) => ({ ...cur, [k]: val }));

  const tpl: TemplateOut | undefined = templateId
    ? templates.data?.find((x) => x.id === templateId)
    : undefined;
  const tv = tpl ? templateValues(tpl) : undefined;

  const exam = v.kind === "exam";
  const eff = effectiveValues(v);
  const examForced = (k: TplKey) =>
    exam && (k === "structure" || k === "visibility" || k === "panel");
  const reason = (k: TplKey | "name" | "template"): string | undefined => {
    if (archived) return locked[LOCK_KEY[k]] ?? "Archived sessions are read-only";
    if (locked[LOCK_KEY[k]]) return locked[LOCK_KEY[k]];
    if (k !== "name" && k !== "template" && examForced(k)) return EXAM_REASON;
    return undefined;
  };
  const isLocked = (k: TplKey | "name" | "template") => !!reason(k);

  function applyTemplate(id: string) {
    setTemplateId(id);
    const t = templates.data?.find((x) => x.id === id);
    if (!t) return; // "No template": keep current values, just unlink.
    const vals = templateValues(t);
    setV((cur) => {
      const next = { ...cur };
      for (const k of TPL_KEYS)
        if (!locked[LOCK_KEY[k]] && !archived)
          (next as Record<string, unknown>)[k] = vals[k];
      return next;
    });
  }

  const setByTemplate = TPL_KEYS.filter((k) => tv && !same(k, tv[k], BASE_VALUES[k])).length;

  /** "From template" / "Changed" tag + reset link, or the lock reason. */
  function note(k: TplKey) {
    const lock = reason(k);
    if (lock) return <LockNote reason={lock} />;
    if (!tv) return null;
    if (!same(k, v[k], tv[k]))
      return (
        <p className="flex items-center gap-2">
          <Tag tone="changed">Changed</Tag>
          <button
            type="button"
            onClick={() => set(k, tv[k] as never)}
            className="text-xs text-bank-accent underline"
          >
            Reset to template
          </button>
        </p>
      );
    if (!same(k, tv[k], BASE_VALUES[k]))
      return (
        <p>
          <Tag tone="tpl">From template</Tag>
        </p>
      );
    return null;
  }

  function submit(ev: React.FormEvent) {
    ev.preventDefault();
    const amount = (x: string) =>
      /^\d{1,16}(\.\d{1,2})?$/.test(x.trim()) && Number(x) > 0
        ? undefined
        : "Enter a positive amount with at most 2 decimals";
    const next = {
      name: v.name.trim() ? undefined : "Enter a session name",
      roles: v.roles.length ? undefined : "Select at least one role",
      capUsd: amount(v.capUsd),
      capSos: sosOn ? amount(v.capSos) : undefined,
      seedProfile:
        v.seedProfile.trim().length > 80 ? "Use at most 80 characters" : undefined,
    };
    setErrors(next);
    if (Object.values(next).some(Boolean)) return;
    onSubmit(
      {
        ...eff,
        name: v.name.trim(),
        capUsd: v.capUsd.trim(),
        capSos: v.capSos.trim(),
        seedProfile: v.seedProfile.trim(),
      },
      templateId,
    );
  }

  const label = (o: { value: string; label: string }[], x: string) =>
    o.find((y) => y.value === x)?.label ?? x;

  return (
    <FormPage
      title={title}
      subtitle={subtitle}
      aside={
        <div className="lg:sticky lg:top-4">
          <SummaryCard
            title="Session Summary"
            rows={[
              { label: "Name", value: v.name.trim() || "--" },
              { label: "Kind", value: label(KIND_OPTS, v.kind) },
              { label: "Structure", value: label(STRUCTURE_OPTS, eff.structure) },
              { label: "Visibility", value: label(VIS_OPTS, eff.visibility) },
              { label: "Roles", value: `${v.roles.length} allowed` },
              { label: "Capital (USD)", value: v.capUsd.trim() || "--" },
              ...(sosOn ? [{ label: "Capital (SOS)", value: v.capSos.trim() || "--" }] : []),
            ]}
          />
        </div>
      }
    >
      <form onSubmit={submit} noValidate className="space-y-6">
        <FormSection title="Session Details">
          <Labeled label="Session name" required error={errors.name}>
            <TextInput
              value={v.name}
              disabled={isLocked("name")}
              onChange={(e) => set("name", e.target.value)}
            />
          </Labeled>
          {reason("name") && <LockNote reason={reason("name")!} />}
          <div className="space-y-1.5">
            <Labeled label="Template" optional>
              <Select
                className="w-full"
                value={templateId}
                onChange={(e) => applyTemplate(e.target.value)}
                disabled={templates.isPending || isLocked("template")}
              >
                <option value="">No template</option>
                {templates.data?.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </Select>
            </Labeled>
            {reason("template") ? (
              <LockNote reason={reason("template")!} />
            ) : tpl ? (
              <p className="text-xs text-text-muted">
                Template set {setByTemplate} {setByTemplate === 1 ? "field" : "fields"}.
                You can still change any of them.
              </p>
            ) : null}
          </div>
          <p className="text-sm font-medium text-text-strong">Kind</p>
          <OptionCards
            label="Kind"
            columns={2}
            options={KIND_OPTS}
            value={v.kind}
            onChange={(x) => set("kind", x)}
            disabled={isLocked("kind")}
          />
          {note("kind")}
          <Labeled
            label="Seed profile"
            optional
            error={errors.seedProfile}
            hint="Optional label for the seed data profile"
          >
            <TextInput
              maxLength={80}
              value={v.seedProfile}
              disabled={isLocked("seedProfile")}
              onChange={(e) => set("seedProfile", e.target.value)}
            />
          </Labeled>
          {note("seedProfile")}
        </FormSection>
        <FormSection title="Bank Setup">
          <p className="text-sm font-medium text-text-strong">Structure</p>
          <OptionCards
            label="Structure"
            columns={2}
            options={STRUCTURE_OPTS}
            value={eff.structure as "single_bank" | "per_group"}
            onChange={(x) => set("structure", x)}
            disabled={isLocked("structure")}
          />
          {note("structure")}
          <p className="text-sm font-medium text-text-strong">Default visibility</p>
          <OptionCards
            label="Default visibility"
            columns={2}
            options={VIS_OPTS}
            value={eff.visibility as "all" | "own"}
            onChange={(x) => set("visibility", x)}
            disabled={isLocked("visibility")}
          />
          {note("visibility")}
          <FormGrid>
            <div className="space-y-1.5">
              <Labeled
                label="Opening capital (USD)"
                required
                error={errors.capUsd}
                hint="Starting capital for each bank in this session."
              >
                <TextInput
                  inputMode="decimal"
                  value={v.capUsd}
                  disabled={isLocked("capUsd")}
                  onChange={(e) => set("capUsd", e.target.value)}
                />
              </Labeled>
              {note("capUsd")}
            </div>
            {sosOn && (
              <div className="space-y-1.5">
                <Labeled label="Opening capital (SOS)" required error={errors.capSos}>
                  <TextInput
                    inputMode="decimal"
                    value={v.capSos}
                    disabled={isLocked("capSos")}
                    onChange={(e) => set("capSos", e.target.value)}
                  />
                </Labeled>
                {note("capSos")}
              </div>
            )}
          </FormGrid>
        </FormSection>
        <FormSection title="Roles and Learning">
          <RolesField
            roles={v.roles}
            onToggle={(r) =>
              set(
                "roles",
                v.roles.includes(r) ? v.roles.filter((x) => x !== r) : [...v.roles, r],
              )
            }
            error={errors.roles}
            disabled={isLocked("roles")}
          />
          {note("roles")}
          <SwitchRow
            title="Dr/Cr learning panel"
            description="After each posting, show students the debit and credit lines it created."
            checked={eff.panel}
            disabled={isLocked("panel")}
            onChange={(x) => set("panel", x)}
          />
          {note("panel")}
        </FormSection>
        <ErrorMsg error={error} />
        <FormActions>
          <Link href={cancelHref} className={buttonVariants({ variant: "outline" })}>
            Cancel
          </Link>
          {!archived && (
            <Button type="submit" disabled={pending}>
              {pending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : submitIcon}
              {pending ? pendingLabel : submitLabel}
            </Button>
          )}
        </FormActions>
      </form>
    </FormPage>
  );
}
