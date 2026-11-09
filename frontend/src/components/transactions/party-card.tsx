"use client";

import { CreditCard, Phone, User } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

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
    <div className="space-y-1.5">
      <label htmlFor={id} className="text-sm font-medium text-text-strong">
        {label}
      </label>
      <div className="relative">
        <Icon
          className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-text-muted"
          aria-hidden
        />
        <Input id={id} aria-invalid={!!error} className="pl-8" {...props} />
      </div>
      {error && (
        <p role="alert" className="text-sm text-fin-danger">
          {error}
        </p>
      )}
    </div>
  );
}

/** Depositor / withdrawer details (required by the API for cash). */
export function PartyCard({
  title,
  value,
  onChange,
  errs,
}: {
  title: string;
  value: Party;
  onChange: (p: Party) => void;
  errs: Record<string, string>;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Field
          id="party-name"
          label="Full Name"
          icon={User}
          placeholder="Enter full name"
          value={value.name}
          error={errs.name}
          onChange={(e) => onChange({ ...value, name: e.target.value })}
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            id="party-id"
            label="ID Number"
            icon={CreditCard}
            placeholder="Enter ID number"
            value={value.idNo}
            error={errs.idNo}
            onChange={(e) => onChange({ ...value, idNo: e.target.value })}
          />
          <Field
            id="party-phone"
            label="Phone"
            icon={Phone}
            inputMode="tel"
            placeholder="Enter phone number"
            value={value.phone}
            error={errs.phone}
            onChange={(e) => onChange({ ...value, phone: e.target.value })}
          />
        </div>
      </CardContent>
    </Card>
  );
}
