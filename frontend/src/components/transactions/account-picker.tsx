"use client";

import { useState } from "react";
import { formatAccountNo } from "@/lib/accounts";
import { formatMoney } from "@/lib/banking";
import { lookupAccount } from "@/lib/transactions";
import type { AccountOut } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { errorText, Labeled } from "@/components/lab/common";

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
    <div className="space-y-2">
      <Labeled label={label} error={err}>
        <div className="flex gap-2">
          <Input
            inputMode="numeric"
            placeholder="Account number"
            value={no}
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
          <Button type="button" variant="outline" disabled={busy} onClick={find}>
            {busy ? "Searching…" : "Find"}
          </Button>
        </div>
      </Labeled>
      {value && (
        <div className="rounded-md border border-border bg-surface px-3 py-2 text-sm">
          <p className="font-medium text-text-strong">
            {value.customer_name}{" "}
            <span className="font-mono text-xs text-text-muted">
              {formatAccountNo(value.account_no)}
            </span>
          </p>
          <p className="text-text-muted">
            {value.product_name} · {value.currency} · Balance{" "}
            <span className="tabular-nums">
              {formatMoney(value.ledger_balance, value.currency)}
            </span>
          </p>
        </div>
      )}
    </div>
  );
}
