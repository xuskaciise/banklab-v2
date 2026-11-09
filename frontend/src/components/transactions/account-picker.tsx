"use client";

import { useState } from "react";
import { Loader2, Search } from "lucide-react";
import { formatAccountNo } from "@/lib/accounts";
import { formatMoney } from "@/lib/banking";
import { lookupAccount } from "@/lib/transactions";
import type { AccountOut } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { errorText, StatusBadge } from "@/components/lab/common";
import { BTN_FIND, FIELD } from "./field-styles";
import { FieldLabel } from "./field-label";
import { CustomerIdentity } from "./customer-identity";

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
        <div className="flex items-stretch gap-2">
          <Input
            id={id}
            inputMode="numeric"
            placeholder="Enter account number"
            value={no}
            aria-invalid={!!err}
            className={FIELD}
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
            variant="ghost"
            disabled={busy}
            onClick={find}
            className={BTN_FIND}
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
      {value && (
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate font-semibold text-text-strong">
                {value.customer_name}
              </p>
              <p className="font-mono text-xs text-text-muted">
                {formatAccountNo(value.account_no)}
              </p>
            </div>
            <StatusBadge status={value.status} />
          </div>
          <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
            <div>
              <dt className="text-xs text-text-muted">Product</dt>
              <dd className="text-text-body">{value.product_name}</dd>
            </div>
            <div>
              <dt className="text-xs text-text-muted">Current balance</dt>
              <dd className="font-semibold text-text-strong tabular-nums">
                {formatMoney(value.ledger_balance, value.currency)}
              </dd>
            </div>
          </dl>
          <div className="mt-3">
            <CustomerIdentity
              sid={sid}
              customerId={value.customer_id}
              mandate={value.mandate}
            />
          </div>
        </div>
      )}
    </div>
  );
}
