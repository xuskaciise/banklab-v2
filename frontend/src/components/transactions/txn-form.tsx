"use client";

import { useState } from "react";
import { useCreateTxn } from "@/lib/transactions";
import type { AccountOut, TransactionOut } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ErrorMsg, Labeled } from "@/components/lab/common";
import { AccountPicker } from "./account-picker";

export type Kind = "deposit" | "withdrawal" | "transfer";

/** Cash deposit / withdrawal / transfer form. Balances come from the API. */
export function TxnForm({
  sid,
  kind,
  onDone,
}: {
  sid: string;
  kind: Kind;
  onDone: (t: TransactionOut) => void;
}) {
  const create = useCreateTxn(sid);
  const cash = kind !== "transfer";
  const [from, setFrom] = useState<AccountOut | null>(null);
  const [to, setTo] = useState<AccountOut | null>(null);
  const [amount, setAmount] = useState("");
  const [party, setParty] = useState({ name: "", idNo: "", phone: "" });
  const [narration, setNarration] = useState("");
  const [errs, setErrs] = useState<Record<string, string>>({});

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const er: Record<string, string> = {};
    if (!from) er.from = "Find the account first";
    if (kind === "transfer") {
      if (!to) er.to = "Find the destination account first";
      else if (from && to.id === from.id) er.to = "Choose a different account";
      else if (from && to.currency !== from.currency)
        er.to = "Accounts must have the same currency";
    }
    const n = Number(amount);
    if (!amount.trim() || !Number.isFinite(n) || n <= 0)
      er.amount = "Enter an amount greater than zero";
    else if (!/^\d+(\.\d{1,2})?$/.test(amount.trim()))
      er.amount = "Use at most two decimals";
    if (cash) {
      if (!party.name.trim()) er.name = "Name is required";
      if (!party.idNo.trim()) er.idNo = "ID number is required";
      if (!party.phone.trim()) er.phone = "Phone is required";
    }
    setErrs(er);
    if (Object.keys(er).length || !from) return;

    const common = {
      amount: amount.trim(),
      currency: from.currency,
      narration: narration.trim(),
    };
    if (kind === "transfer") {
      create.mutate(
        {
          kind,
          body: { ...common, from_account_id: from.id, to_account_id: to!.id },
        },
        { onSuccess: onDone },
      );
    } else {
      create.mutate(
        {
          kind,
          body: {
            ...common,
            account_id: from.id,
            party_name: party.name.trim(),
            party_id_no: party.idNo.trim(),
            party_phone: party.phone.trim(),
          },
        },
        { onSuccess: onDone },
      );
    }
  }

  return (
    <form onSubmit={submit} className="max-w-xl space-y-4" noValidate>
      <AccountPicker
        sid={sid}
        label={kind === "transfer" ? "From account" : "Account number"}
        value={from}
        onChange={setFrom}
      />
      {errs.from && <p className="text-sm text-fin-danger">{errs.from}</p>}
      {kind === "transfer" && (
        <>
          <AccountPicker sid={sid} label="To account" value={to} onChange={setTo} />
          {errs.to && <p className="text-sm text-fin-danger">{errs.to}</p>}
        </>
      )}
      <Labeled
        label={`Amount${from ? ` (${from.currency})` : ""}`}
        error={errs.amount}
      >
        <Input
          inputMode="decimal"
          placeholder="0.00"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
        />
      </Labeled>
      {cash && (
        <fieldset className="space-y-3 rounded-lg border border-border p-4">
          <legend className="px-1 text-xs font-medium text-text-muted uppercase">
            {kind === "deposit" ? "Depositor" : "Person collecting cash"}
          </legend>
          <Labeled label="Full name" error={errs.name}>
            <Input
              value={party.name}
              onChange={(e) => setParty({ ...party, name: e.target.value })}
            />
          </Labeled>
          <div className="grid gap-3 sm:grid-cols-2">
            <Labeled label="ID number" error={errs.idNo}>
              <Input
                value={party.idNo}
                onChange={(e) => setParty({ ...party, idNo: e.target.value })}
              />
            </Labeled>
            <Labeled label="Phone" error={errs.phone}>
              <Input
                value={party.phone}
                onChange={(e) => setParty({ ...party, phone: e.target.value })}
              />
            </Labeled>
          </div>
        </fieldset>
      )}
      <Labeled label="Narration (optional)">
        <Input value={narration} onChange={(e) => setNarration(e.target.value)} />
      </Labeled>
      <ErrorMsg error={create.error} />
      <Button type="submit" disabled={create.isPending}>
        {create.isPending ? "Posting…" : "Submit"}
      </Button>
    </form>
  );
}
