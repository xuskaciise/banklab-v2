"use client";

import { Check } from "lucide-react";
import { BANK_ROLES, ROLE_LABEL } from "@/lib/lab";
import { cn } from "@/lib/utils";

const ROLE_HINT: Record<string, string> = {
  teller: "Cash deposits, withdrawals and the till",
  cso: "Customers, accounts and transfers",
  manager: "Approvals, tills and end of day",
  vault_custodian: "Vault cash and cash movements",
  accountant: "Ledger and financial reports",
};

const FOCUS =
  "outline-none focus-visible:ring-2 focus-visible:ring-bank-accent focus-visible:ring-offset-2";

/** Required multi-select of the roles allowed in a session, as toggle cards. */
export function RolesField({
  roles,
  onToggle,
  error,
}: {
  roles: string[];
  onToggle: (r: string) => void;
  error?: string;
}) {
  return (
    <fieldset className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <legend className="text-sm font-medium text-text-strong">
          Allowed roles
          <span aria-hidden className="ml-0.5 text-fin-danger">
            *
          </span>
          <span className="sr-only"> (required)</span>
        </legend>
        <span className="text-xs text-text-muted">
          {roles.length} of {BANK_ROLES.length} selected
        </span>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {BANK_ROLES.map((r) => {
          const on = roles.includes(r);
          return (
            <button
              key={r}
              type="button"
              role="checkbox"
              aria-checked={on}
              onClick={() => onToggle(r)}
              className={cn(
                "flex items-start gap-3 rounded-lg border p-3 text-left transition-colors",
                FOCUS,
                on
                  ? "border-bank-primary bg-bank-sky-light"
                  : "border-border bg-card hover:bg-hover",
              )}
            >
              <span
                aria-hidden
                className={cn(
                  "mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-md border transition-colors",
                  on
                    ? "border-bank-primary bg-bank-primary text-white"
                    : "border-border bg-card",
                )}
              >
                {on && <Check className="size-3.5" strokeWidth={3} />}
              </span>
              <span className="min-w-0">
                <span className="block text-sm font-semibold text-text-strong">
                  {ROLE_LABEL[r]}
                </span>
                <span className="block text-xs text-text-muted">{ROLE_HINT[r]}</span>
              </span>
            </button>
          );
        })}
      </div>
      {error && (
        <p role="alert" className="text-sm text-fin-danger">
          {error}
        </p>
      )}
    </fieldset>
  );
}

/** On/off row with a title, an explanation and a switch. */
export function SwitchRow({
  title,
  description,
  checked,
  disabled,
  note,
  onChange,
}: {
  title: string;
  description: string;
  checked: boolean;
  disabled?: boolean;
  note?: string;
  onChange: (v: boolean) => void;
}) {
  return (
    <div
      className={cn(
        "flex items-center justify-between gap-4 rounded-lg border border-border p-4",
        disabled ? "bg-surface" : "bg-card",
      )}
    >
      <div className="min-w-0">
        <p className="text-sm font-semibold text-text-strong">{title}</p>
        <p className="text-xs text-text-muted">{description}</p>
        {disabled && note && <p className="mt-1 text-xs text-text-body">{note}</p>}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={title}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors disabled:cursor-not-allowed disabled:opacity-50",
          FOCUS,
          checked ? "bg-bank-primary" : "bg-border",
        )}
      >
        <span
          aria-hidden
          className={cn(
            "inline-block size-5 rounded-full bg-card shadow-xs transition-transform",
            checked ? "translate-x-5.5" : "translate-x-0.5",
          )}
        />
      </button>
    </div>
  );
}
