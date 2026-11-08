"use client";

import { Plus, Trash2 } from "lucide-react";
import { DOC_TYPES, RELATION_LABEL } from "@/lib/customers";
import type { DocumentIn, KinIn } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/shared/checkbox";
import { Labeled, Select } from "@/components/lab/common";

export type PersonDraft = {
  full_name: string;
  sex: string;
  date_of_birth: string;
  phone: string;
  relation: string;
  can_sign: boolean;
  docs: DocumentIn[];
  kin: KinIn[];
};

export const emptyDoc = (): DocumentIn => ({
  type: "national_id",
  number: "",
  issue_date: "",
  expiry_date: "",
});
export const emptyKin = (): KinIn => ({ name: "", phone: "", relationship: "" });
export const emptyPerson = (relation: string): PersonDraft => ({
  full_name: "",
  sex: "",
  date_of_birth: "",
  phone: "",
  relation,
  can_sign: false,
  docs: [emptyDoc()],
  kin: [],
});

export function validateDoc(d: DocumentIn): string | null {
  if (!d.number.trim()) return "Enter the ID document number";
  if (!d.issue_date || !d.expiry_date)
    return "Enter the issue and expiry dates of the ID document";
  if (d.expiry_date <= d.issue_date)
    return "ID document expiry must be after the issue date";
  return null;
}

export function validatePerson(p: PersonDraft, label: string): string | null {
  if (!p.full_name.trim()) return `${label}: enter the full name`;
  if (!p.sex) return `${label}: select the sex`;
  if (!p.date_of_birth) return `${label}: enter the date of birth`;
  if (!p.phone.trim()) return `${label}: enter the phone number`;
  if (p.docs.length < 1) return `${label}: add at least one ID document`;
  for (const d of p.docs) {
    const e = validateDoc(d);
    if (e) return `${label}: ${e}`;
  }
  for (const k of p.kin)
    if (!k.name.trim() || !k.phone.trim() || !k.relationship.trim())
      return `${label}: complete or remove the next of kin entry`;
  return null;
}

export function DocFields({
  value,
  onChange,
  onRemove,
}: {
  value: DocumentIn;
  onChange: (d: DocumentIn) => void;
  onRemove?: () => void;
}) {
  const set = (k: keyof DocumentIn, v: string) => onChange({ ...value, [k]: v });
  return (
    <div className="grid gap-3 rounded-lg border border-border bg-surface p-3 sm:grid-cols-2">
      <Labeled label="Document type">
        <Select
          className="w-full"
          value={value.type}
          onChange={(e) => set("type", e.target.value)}
        >
          {DOC_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </Select>
      </Labeled>
      <Labeled label="Number">
        <Input value={value.number} onChange={(e) => set("number", e.target.value)} />
      </Labeled>
      <Labeled label="Issue date">
        <Input
          type="date"
          value={value.issue_date}
          onChange={(e) => set("issue_date", e.target.value)}
        />
      </Labeled>
      <Labeled label="Expiry date">
        <Input
          type="date"
          value={value.expiry_date}
          onChange={(e) => set("expiry_date", e.target.value)}
        />
      </Labeled>
      {onRemove && (
        <div className="sm:col-span-2">
          <Button type="button" variant="ghost" size="sm" onClick={onRemove}>
            <Trash2 /> Remove document
          </Button>
        </div>
      )}
    </div>
  );
}

export function KinFields({
  value,
  onChange,
  onRemove,
}: {
  value: KinIn;
  onChange: (k: KinIn) => void;
  onRemove?: () => void;
}) {
  const set = (k: keyof KinIn, v: string) => onChange({ ...value, [k]: v });
  return (
    <div className="grid gap-3 rounded-lg border border-border bg-surface p-3 sm:grid-cols-3">
      <Labeled label="Name">
        <Input value={value.name} onChange={(e) => set("name", e.target.value)} />
      </Labeled>
      <Labeled label="Phone">
        <Input value={value.phone} onChange={(e) => set("phone", e.target.value)} />
      </Labeled>
      <Labeled label="Relationship">
        <Input
          value={value.relationship}
          onChange={(e) => set("relationship", e.target.value)}
        />
      </Labeled>
      {onRemove && (
        <div className="sm:col-span-3">
          <Button type="button" variant="ghost" size="sm" onClick={onRemove}>
            <Trash2 /> Remove next of kin
          </Button>
        </div>
      )}
    </div>
  );
}

/** Editable person block: identity, ID documents and optional next of kin. */
export function PersonFields({
  value,
  onChange,
  relationOptions,
}: {
  value: PersonDraft;
  onChange: (p: PersonDraft) => void;
  /** When more than one, a relation selector is shown. */
  relationOptions: string[];
}) {
  const set = <K extends keyof PersonDraft>(k: K, v: PersonDraft[K]) =>
    onChange({ ...value, [k]: v });
  const showRelation = relationOptions.length > 1;
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <Labeled label="Full name">
          <Input
            value={value.full_name}
            onChange={(e) => set("full_name", e.target.value)}
          />
        </Labeled>
        <Labeled label="Phone">
          <Input value={value.phone} onChange={(e) => set("phone", e.target.value)} />
        </Labeled>
        <Labeled label="Sex">
          <Select
            className="w-full"
            value={value.sex}
            onChange={(e) => set("sex", e.target.value)}
          >
            <option value="">Select…</option>
            <option value="male">Male</option>
            <option value="female">Female</option>
          </Select>
        </Labeled>
        <Labeled label="Date of birth">
          <Input
            type="date"
            value={value.date_of_birth}
            onChange={(e) => set("date_of_birth", e.target.value)}
          />
        </Labeled>
        {showRelation && (
          <Labeled label="Role in customer">
            <Select
              className="w-full"
              value={value.relation}
              onChange={(e) => set("relation", e.target.value)}
            >
              {relationOptions.map((r) => (
                <option key={r} value={r}>
                  {RELATION_LABEL[r] ?? r}
                </option>
              ))}
            </Select>
          </Labeled>
        )}
        {showRelation && value.relation === "director" && (
          <label className="flex items-center gap-2 self-end pb-2 text-sm text-text-strong">
            <Checkbox
              checked={value.can_sign}
              onChange={(e) => set("can_sign", e.target.checked)}
            />
            Can sign
          </label>
        )}
      </div>

      <section className="space-y-2">
        <p className="text-xs font-medium tracking-wide text-text-muted uppercase">
          ID documents (at least one)
        </p>
        {value.docs.map((d, i) => (
          <DocFields
            key={i}
            value={d}
            onChange={(nd) =>
              set("docs", value.docs.map((x, j) => (j === i ? nd : x)))
            }
            onRemove={
              value.docs.length > 1
                ? () => set("docs", value.docs.filter((_, j) => j !== i))
                : undefined
            }
          />
        ))}
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => set("docs", [...value.docs, emptyDoc()])}
        >
          <Plus /> Add document
        </Button>
      </section>

      <section className="space-y-2">
        <p className="text-xs font-medium tracking-wide text-text-muted uppercase">
          Next of kin (optional)
        </p>
        {value.kin.map((k, i) => (
          <KinFields
            key={i}
            value={k}
            onChange={(nk) => set("kin", value.kin.map((x, j) => (j === i ? nk : x)))}
            onRemove={() => set("kin", value.kin.filter((_, j) => j !== i))}
          />
        ))}
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => set("kin", [...value.kin, emptyKin()])}
        >
          <Plus /> Add next of kin
        </Button>
      </section>
    </div>
  );
}
