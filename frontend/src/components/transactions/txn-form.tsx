"use client";

import { useEffect, useState } from "react";
import { useCustomer } from "@/lib/customers";
import { useCreateTxn } from "@/lib/transactions";
import type { AccountOut, TransactionOut } from "@/lib/api/types";
import { Input, Textarea } from "@/components/ui/input";
import { AccountPicker } from "./account-picker";
import { AmountField } from "./amount-field";
import { FieldLabel } from "./field-label";
import { Panel } from "./panel";
import { PartyCard, type Party } from "./party-card";
import { TxnActions } from "./txn-actions";
import { TxnSummary } from "./txn-summary";
import type { Kind } from "./type-selector";

export type { Kind };

/** Cheque numbers are whole numbers (digits only). */
function chequeError(v: string): string | undefined {
  const c = v.trim();
  if (!c) return undefined;
  if (!/^d+$/.test(c) || !(Number(c) > 0)) return "Cheque number must be a whole number";
  return undefined;
}

const COL = "min-h-0 space-y-3 lg:overflow-y-auto lg:pr-1";

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
  const [chequeNo, setChequeNo] = useState("");
  const [party, setParty] = useState<Party>({ name: "", idNo: "", phone: "" });
  const [same, setSame] = useState(false);
  const [narration, setNarration] = useState("");
  const [resetKey, setResetKey] = useState(0);
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [attempted, setAttempted] = useState(false);

  // Customer data is already cached by the profile card; used to prefill the party.
  const cust = useCustomer(
    { kind: "student", sessionId: sid },
    from?.customer_id ?? "",
    !!from && cash,
  );
  const holder = cust.data?.parties.find((p) => p.can_sign) ?? cust.data?.parties[0];
  const holderKey = holder?.party_id ?? "";
  useEffect(() => {
    if (!same || !holder || !cust.data) return;
    // Prefill from the account holder; the fields stay editable afterwards.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setParty({
      name: holder.full_name,
      idNo: holder.identity_documents[0]?.number ?? "",
      phone: cust.data.phone || holder.phone || "",
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [same, holderKey]);

  const errs: Record<string, string> = {};
  if (kind === "transfer" && from && to) {
    if (to.id === from.id) errs.to = "Choose a different account";
    else if (to.currency !== from.currency)
      errs.to = "Accounts must have the same currency";
  }
  const show = (f: string) => attempted || touched[f];
  const partyErrs: Record<string, string> = {};
  if (cash) {
    if (show("name") && !party.name.trim()) partyErrs.name = "Name is required";
    if (show("idNo") && !party.idNo.trim()) partyErrs.idNo = "ID number is required";
    if (show("phone") && !party.phone.trim()) partyErrs.phone = "Phone is required";
  }
  if (attempted && !from) errs.from = "Find the account first";
  if (attempted && kind === "transfer" && !to && !errs.to)
    errs.to = "Find the destination account first";
  let amtErr = amountError(amount);
  if (!amtErr && attempted && !amount.trim()) amtErr = "Enter an amount greater than zero";
  const isCheque = kind === "cheque_withdrawal";
  let chequeErr = chequeError(chequeNo);
  if (!chequeErr && attempted && isCheque && !chequeNo.trim())
    chequeErr = "Cheque number is required";
  const noCheques = isCheque && !!from && !from.product_allows_cheques;
  if (noCheques) errs.from = "This account's product does not allow cheques";
  const chequeOk = !isCheque || (!!chequeNo.trim() && !chequeErr && !noCheques);
  const amountValid = !!amount.trim() && !amtErr;
  const partyOk = !cash || (party.name.trim() && party.idNo.trim() && party.phone.trim());
  const valid =
    !!from && (kind !== "transfer" || !!to) && !errs.to && amountValid && !!partyOk && chequeOk;
  const noAccount = !from || (kind === "transfer" && !to);

  function reset() {
    setFrom(null);
    setTo(null);
    setAmount("");
    setChequeNo("");
    setParty({ name: "", idNo: "", phone: "" });
    setSame(false);
    setNarration("");
    setTouched({});
    setAttempted(false);
    setResetKey((k) => k + 1);
    create.reset();
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (create.isPending) return;
    if (!valid || !from) return setAttempted(true);
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
      const body = {
        ...common,
        account_id: from.id,
        party_name: party.name.trim(),
        party_id_no: party.idNo.trim(),
        party_phone: party.phone.trim(),
      };
      create.mutate(
        kind === "cheque_withdrawal"
          ? { kind, body: { ...body, cheque_no: Number(chequeNo.trim()) } }
          : { kind, body },
        { onSuccess: onDone },
      );
    }
  }

  const holderLabel =
    kind === "deposit"
      ? "Depositor is the account holder"
      : "Withdrawer is the account holder";
  const actions = (
    <TxnActions
      kind={kind}
      valid={valid}
      pending={create.isPending}
      error={create.error}
      onReset={reset}
    />
  );

  return (
    <form
      onSubmit={submit}
      noValidate
      className="grid gap-3 lg:min-h-0 lg:flex-1 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)_minmax(300px,0.8fr)]"
    >
      <div className={COL}>
        <Panel title={kind === "transfer" ? "Source Account" : "Account & Customer"}>
          <AccountPicker
            key={`from-${resetKey}`}
            sid={sid}
            label={kind === "transfer" ? "From Account" : "Account Number"}
            value={from}
            onChange={setFrom}
            error={errs.from}
            emptyHint="Search an account to see customer details"
          />
        </Panel>
      </div>

      <div className={COL}>
        {kind === "transfer" && (
          <Panel title="Destination Account">
            <AccountPicker
              key={`to-${resetKey}`}
              sid={sid}
              label="To Account"
              value={to}
              onChange={setTo}
              error={errs.to}
              emptyHint="Search the destination account"
            />
          </Panel>
        )}
        <Panel title="Transaction">
          {isCheque && (
            <div className="space-y-1">
              <FieldLabel htmlFor="txn-cheque-no" required>
                Cheque Number
              </FieldLabel>
              <Input
                id="txn-cheque-no"
                inputMode="numeric"
                autoComplete="off"
                placeholder="e.g. 1001"
                value={chequeNo}
                disabled={noAccount}
                aria-invalid={!!chequeErr}
                onChange={(e) => setChequeNo(e.target.value)}
                onBlur={() => setTouched((t) => ({ ...t, cheque: true }))}
                className="font-mono"
              />
              {(attempted || touched.cheque || chequeNo.trim()) && chequeErr && (
                <p role="alert" className="text-xs text-fin-danger">
                  {chequeErr}
                </p>
              )}
            </div>
          )}
          <AmountField
            value={amount}
            onChange={setAmount}
            currency={from?.currency}
            error={amtErr}
            disabled={noAccount}
          />
        </Panel>
        {cash && (
          <PartyCard
            title={kind === "deposit" ? "Depositor Information" : "Withdrawer Information"}
            holderLabel={holderLabel}
            same={same}
            onSame={setSame}
            value={party}
            onChange={setParty}
            errs={partyErrs}
            onBlurField={(f) => setTouched((t) => ({ ...t, [f]: true }))}
            disabled={noAccount}
          />
        )}
        <Panel>
          <div className="space-y-1">
            <FieldLabel htmlFor="txn-narration" optional>
              Narration
            </FieldLabel>
            <Textarea
              id="txn-narration"
              rows={2}
              placeholder="Enter transaction description..."
              value={narration}
              disabled={noAccount}
              onChange={(e) => setNarration(e.target.value)}
              className="min-h-0 resize-none py-2"
            />
          </div>
        </Panel>
      </div>

      <TxnSummary
        kind={kind}
        from={from}
        to={to}
        amount={amount}
        amountValid={amountValid}
        chequeNo={chequeNo}
        dateLabel={dateLabel}
        actions={actions}
      />
    </form>
  );
}
