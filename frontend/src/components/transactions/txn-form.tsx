"use client";

import { useState } from "react";
import { ArrowDownToLine, ArrowLeftRight, ArrowUpFromLine, Loader2 } from "lucide-react";
import { useCreateTxn } from "@/lib/transactions";
import type { AccountOut, TransactionOut } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorMsg } from "@/components/lab/common";
import { AccountLookupCard } from "./account-lookup-card";
import { AmountField } from "./amount-field";
import { PartyCard, type Party } from "./party-card";
import { TxnSummary } from "./txn-summary";
import type { Kind } from "./type-selector";

export type { Kind };

const SUBMIT: Record<Kind, { label: string; icon: typeof ArrowDownToLine }> = {
  deposit: { label: "Submit Deposit", icon: ArrowDownToLine },
  withdrawal: { label: "Submit Withdrawal", icon: ArrowUpFromLine },
  transfer: { label: "Submit Transfer", icon: ArrowLeftRight },
};

/** Amount must be > 0 with at most two decimals. */
function amountError(amount: string): string | undefined {
  const a = amount.trim();
  if (!a) return undefined;
  if (!/^\d+(\.\d{1,2})?$/.test(a)) return "Use a number with at most two decimals";
  if (!(Number(a) > 0)) return "Enter an amount greater than zero";
  return undefined;
}

/** Cash deposit / withdrawal / transfer form. Balances come from the API. */
export function TxnForm({
  sid,
  kind,
  dateLabel,
  onDone,
}: {
  sid: string;
  kind: Kind;
  dateLabel: string;
  onDone: (t: TransactionOut) => void;
}) {
  const create = useCreateTxn(sid);
  const cash = kind !== "transfer";
  const [from, setFrom] = useState<AccountOut | null>(null);
  const [to, setTo] = useState<AccountOut | null>(null);
  const [amount, setAmount] = useState("");
  const [party, setParty] = useState<Party>({ name: "", idNo: "", phone: "" });
  const [narration, setNarration] = useState("");
  const [resetKey, setResetKey] = useState(0);

  const errs: Record<string, string> = {};
  if (kind === "transfer" && from && to) {
    if (to.id === from.id) errs.to = "Choose a different account";
    else if (to.currency !== from.currency)
      errs.to = "Accounts must have the same currency";
  }
  const amtErr = amountError(amount);
  const amountValid = !!amount.trim() && !amtErr;
  const partyOk = !cash || (party.name.trim() && party.idNo.trim() && party.phone.trim());
  const valid =
    !!from && (kind !== "transfer" || !!to) && !errs.to && amountValid && !!partyOk;

  function reset() {
    setFrom(null);
    setTo(null);
    setAmount("");
    setParty({ name: "", idNo: "", phone: "" });
    setNarration("");
    setResetKey((k) => k + 1);
    create.reset();
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!valid || !from || create.isPending) return;
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

  const { label, icon: Icon } = SUBMIT[kind];
  return (
    <form
      onSubmit={submit}
      noValidate
      className="grid gap-6 lg:grid-cols-[minmax(0,13fr)_minmax(0,7fr)]"
    >
      <div className="space-y-6">
        <AccountLookupCard
          key={resetKey}
          sid={sid}
          transfer={kind === "transfer"}
          from={from}
          to={to}
          onFrom={setFrom}
          onTo={setTo}
          errs={errs}
        />
        <AmountField
          value={amount}
          onChange={setAmount}
          currency={from?.currency}
          error={amtErr}
        />
        {cash && (
          <PartyCard
            title={kind === "deposit" ? "Depositor Information" : "Withdrawer Information"}
            value={party}
            onChange={setParty}
            errs={{}}
          />
        )}
        <Card>
          <CardHeader>
            <CardTitle>
              <label htmlFor="txn-narration">Narration</label>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <textarea
              id="txn-narration"
              rows={3}
              placeholder="Enter transaction description..."
              value={narration}
              onChange={(e) => setNarration(e.target.value)}
              className="w-full resize-y rounded-lg border border-border bg-card px-3 py-2 text-sm text-text-body outline-none transition-colors placeholder:text-text-muted focus-visible:border-bank-accent focus-visible:ring-2 focus-visible:ring-bank-accent/40"
            />
            <p className="mt-1 text-xs text-text-muted">Optional.</p>
          </CardContent>
        </Card>
        <ErrorMsg error={create.error} />
        <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-end">
          {!valid && (
            <p className="text-xs text-text-muted sm:mr-auto">
              Find the account{kind === "transfer" ? "s" : ""}, enter an amount
              {cash ? " and the party details" : ""} to continue.
            </p>
          )}
          <Button
            type="button"
            variant="outline"
            onClick={reset}
            disabled={create.isPending}
            className="focus-visible:ring-bank-accent"
          >
            Cancel
          </Button>
          <Button
            type="submit"
            disabled={!valid || create.isPending}
            className="bg-bank-primary text-white hover:bg-bank-navy focus-visible:ring-bank-accent"
          >
            {create.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Icon className="size-4" aria-hidden />
            )}
            {create.isPending ? "Posting…" : label}
          </Button>
        </div>
      </div>
      <aside>
        <TxnSummary
          kind={kind}
          from={from}
          to={to}
          amount={amount}
          amountValid={amountValid}
          dateLabel={dateLabel}
        />
      </aside>
    </form>
  );
}
