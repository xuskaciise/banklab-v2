"use client";

import { useState } from "react";
import { Loader2, Search } from "lucide-react";
import { lookupAccount } from "@/lib/transactions";
import type { AccountOut } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { errorText } from "@/components/lab/common";
import { FieldLabel } from "./field-label";
import { CustomerProfile } from "./customer-profile";

/** Looks an active account up by number; reports the match to the parent. */
export function AccountPicker({
  sid,
  label,
  value,
  onChange,
}: {
  sid: string;
  label: string;
  value: AccountOut | null;
  onChange: (a: AccountOut | null) => void;
}) {
  const [no, setNo] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | undefined>();
  const id = `acct-${label.replace(/\W+/g, "-").toLowerCase()}`;

  async function find() {
    setErr(undefined);
    if (!/^\d+$/.test(no.trim())) return setErr("Enter the account number");
    setBusy(true);
    try {
      const a = await lookupAccount(sid, no);
      if (!a) setErr("No active account with this number");
      onChange(a);
    } catch (e) {
      setErr(errorText(e));
      onChange(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <FieldLabel htmlFor={id} required>
          {label}
        </FieldLabel>
        <div className="flex items-center gap-2">
          <Input
            id={id}
            inputMode="numeric"
            placeholder="Enter account number"
            value={no}
            aria-invalid={!!err}
            onChange={(e) => {
              setNo(e.target.value);
              if (value) onChange(null);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                void find();
              }
            }}
          />
          <Button
            type="button"
            variant="secondary"
            disabled={busy}
            onClick={find}
          >
            {busy ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Search className="size-4" aria-hidden />
            )}
            {busy ? "Searching…" : "Find account"}
          </Button>
        </div>
        {err && (
          <p role="alert" className="text-sm text-fin-danger">
            {err}
          </p>
        )}
      </div>
      {value && <CustomerProfile sid={sid} account={value} />}
    </div>
  );
}
