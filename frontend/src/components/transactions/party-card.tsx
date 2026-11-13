"use client";

import { CreditCard, Phone, User } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/shared/checkbox";
import { FieldLabel } from "./field-label";
import { Panel } from "./panel";

export type Party = { name: string; idNo: string; phone: string };

function Field({
  id,
  label,
  icon: Icon,
  error,
  ...props
}: {
  id: string;
  label: string;
  icon: typeof User;
  error?: string;
} & React.ComponentProps<"input">) {
  return (
    <div className="space-y-1">
      <FieldLabel htmlFor={id} required>
        {label}
      </FieldLabel>
      <div className="relative">
        <Icon
          className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-text-muted"
          aria-hidden
        />
        <Input id={id} aria-invalid={!!error} className="h-9 pl-9" {...props} />
      </div>
      {error && (
        <p role="alert" className="text-xs text-fin-danger">
          {error}
        </p>
      )}
    </div>
  );
}

/** Depositor / withdrawer details (required by the API for cash). */
export function PartyCard({
  title,
  holderLabel,
  same,
  onSame,
  value,
  onChange,
  errs,
  onBlurField,
  disabled,
}: {
  title: string;
  holderLabel: string;
  same: boolean;
  onSame: (v: boolean) => void;
  value: Party;
  onChange: (p: Party) => void;
  errs: Record<string, string>;
  onBlurField: (f: string) => void;
  disabled?: boolean;
}) {
  return (
    <Panel title={title}>
      <label className="flex items-center gap-2 text-sm text-text-body">
        <Checkbox
          checked={same}
          disabled={disabled}
          onChange={(e) => onSame(e.target.checked)}
        />
        {holderLabel}
      </label>
      <Field
        id="party-name"
        label="Full Name"
        icon={User}
        placeholder="Enter full name"
        disabled={disabled}
        value={value.name}
        error={errs.name}
        onBlur={() => onBlurField("name")}
        onChange={(e) => onChange({ ...value, name: e.target.value })}
      />
      <div className="grid gap-3 sm:grid-cols-2">
        <Field
          id="party-id"
          label="ID Number"
          icon={CreditCard}
          placeholder="Enter ID number"
          disabled={disabled}
          value={value.idNo}
          error={errs.idNo}
          onBlur={() => onBlurField("idNo")}
          onChange={(e) => onChange({ ...value, idNo: e.target.value })}
        />
        <Field
          id="party-phone"
          label="Phone"
          icon={Phone}
          inputMode="tel"
          placeholder="Enter phone number"
          disabled={disabled}
          value={value.phone}
          error={errs.phone}
          onBlur={() => onBlurField("phone")}
          onChange={(e) => onChange({ ...value, phone: e.target.value })}
        />
      </div>
    </Panel>
  );
}
