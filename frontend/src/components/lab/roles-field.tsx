"use client";

import { BANK_ROLES, ROLE_LABEL } from "@/lib/lab";
import { Checkbox } from "@/components/shared/checkbox";

/** Required checkbox group of the roles allowed in a session. */
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
    <fieldset className="space-y-2">
      <legend className="text-sm font-medium text-text-strong">
        Allowed roles
        <span aria-hidden className="ml-0.5 text-fin-danger">
          *
        </span>
        <span className="sr-only"> (required)</span>
      </legend>
      <div className="flex flex-wrap gap-4">
        {BANK_ROLES.map((r) => (
          <label key={r} className="flex items-center gap-2 text-sm">
            <Checkbox checked={roles.includes(r)} onChange={() => onToggle(r)} />
            {ROLE_LABEL[r]}
          </label>
        ))}
      </div>
      {error && <p className="text-sm text-fin-danger">{error}</p>}
    </fieldset>
  );
}
