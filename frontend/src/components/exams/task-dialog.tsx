"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/input";
import { ErrorMsg, Labeled, Select, TextInput } from "@/components/lab/common";
import type { CheckType, ExamTask, ExamTaskIn } from "@/lib/api/types";
import { fmtPoints, PRODUCT_CODES } from "@/lib/exams";
import { TYPE_LABEL } from "@/lib/transactions";

const TXN_TYPES = ["cash_deposit", "cash_withdrawal", "transfer", "cheque_withdrawal"];
const CUSTOMER_TYPES = ["individual", "company", "joint", "ngo"];
const CURRENCIES = ["USD", "SOS"];

type P = {
  account: string;
  seed_index: string;
  product_code: string;
  mode: "amount" | "delta";
  amount: string;
  currency: string;
  type: string;
  min_count: string;
};

const EMPTY: P = {
  account: "seed",
  seed_index: "0",
  product_code: "",
  mode: "amount",
  amount: "",
  currency: "",
  type: "",
  min_count: "1",
};

function fromParams(raw: Record<string, unknown>): P {
  const s = (v: unknown) => (v === undefined || v === null ? "" : String(v));
  return {
    account: s(raw.account) || "seed",
    seed_index: s(raw.seed_index) || "0",
    product_code: s(raw.product_code),
    mode: raw.delta !== undefined ? "delta" : "amount",
    amount: s(raw.delta !== undefined ? raw.delta : raw.amount),
    currency: s(raw.currency),
    type: s(raw.type),
    min_count: s(raw.min_count) || "1",
  };
}

/** Builds check_params for one check type; returns an error text or params. */
function buildParams(
  check: string,
  p: P,
): { params?: Record<string, unknown>; error?: string } {
  const isNum = (v: string) => v.trim() !== "" && Number.isFinite(Number(v));
  const count = Number(p.min_count);
  if (check === "account_balance_equals") {
    if (!isNum(p.amount)) return { error: "Enter the expected amount." };
    const out: Record<string, unknown> = { account: p.account };
    if (p.account === "seed") {
      out.seed_index = Number(p.seed_index);
      out[p.mode] = p.amount.trim();
    } else {
      out.amount = p.amount.trim();
      if (p.product_code) out.product_code = p.product_code;
    }
    if (p.currency) out.currency = p.currency;
    return { params: out };
  }
  if (check === "txn_exists") {
    if (!p.type) return { error: "Choose a transaction type." };
    if (!isNum(p.amount) || Number(p.amount) <= 0) return { error: "Enter a positive amount." };
    if (!p.currency) return { error: "Choose a currency." };
    if (!Number.isInteger(count) || count < 1) return { error: "Minimum count must be 1 or more." };
    return {
      params: { type: p.type, amount: p.amount.trim(), currency: p.currency, min_count: count },
    };
  }
  if (check === "till_closed_balanced")
    return { params: p.currency ? { currency: p.currency } : {} };
  if (check === "customer_created") {
    if (!Number.isInteger(count) || count < 1) return { error: "Minimum count must be 1 or more." };
    const out: Record<string, unknown> = { min_count: count };
    if (p.type) out.type = p.type;
    return { params: out };
  }
  return { error: "Unknown check type." };
}

const labelOf = (t: string) => t.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

function CurrencySelect({
  value,
  onChange,
  optional,
}: {
  value: string;
  onChange: (v: string) => void;
  optional?: boolean;
}) {
  return (
    <Select className="w-full" value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">{optional ? "Any currency" : "Select…"}</option>
      {CURRENCIES.map((c) => (
        <option key={c} value={c}>
          {c}
        </option>
      ))}
    </Select>
  );
}

export function TaskDialog({
  open,
  onOpenChange,
  task,
  checkTypes,
  pending,
  error,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  task: ExamTask | null;
  checkTypes: CheckType[];
  pending: boolean;
  error: unknown;
  onSubmit: (body: ExamTaskIn) => void;
}) {
  const [title, setTitle] = useState(task?.title ?? "");
  const [instructions, setInstructions] = useState(task?.instructions ?? "");
  const [check, setCheck] = useState(task?.check_type ?? checkTypes[0]?.name ?? "");
  const [points, setPoints] = useState(task ? fmtPoints(task.points) : "10");
  const [p, setP] = useState<P>(task ? fromParams(task.check_params) : EMPTY);
  const [errs, setErrs] = useState<Record<string, string>>({});
  const set = (patch: Partial<P>) => setP((x) => ({ ...x, ...patch }));

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const next: Record<string, string> = {};
    if (!title.trim()) next.title = "Title is required.";
    const pts = Number(points);
    if (points.trim() === "" || !Number.isFinite(pts) || pts <= 0)
      next.points = "Points must be greater than 0.";
    const built = buildParams(check, p);
    if (built.error) next.params = built.error;
    setErrs(next);
    if (Object.keys(next).length) return;
    onSubmit({
      title: title.trim(),
      instructions: instructions.trim(),
      check_type: check,
      check_params: built.params ?? {},
      points: points.trim(),
    });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{task ? "Edit task" : "Add task"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4" noValidate>
          <Labeled label="Title" required error={errs.title}>
            <TextInput value={title} onChange={(e) => setTitle(e.target.value)} />
          </Labeled>
          <Labeled label="Instructions shown to the student" optional>
            <Textarea value={instructions} onChange={(e) => setInstructions(e.target.value)} />
          </Labeled>
          <div className="grid gap-4 sm:grid-cols-[1fr_8rem]">
            <Labeled label="Check type" required>
              <Select
                className="w-full"
                value={check}
                onChange={(e) => {
                  setCheck(e.target.value);
                  setP(EMPTY);
                }}
              >
                {checkTypes.map((t) => (
                  <option key={t.name} value={t.name}>
                    {t.label}
                  </option>
                ))}
              </Select>
            </Labeled>
            <Labeled label="Points" required error={errs.points}>
              <TextInput
                inputMode="decimal"
                value={points}
                onChange={(e) => setPoints(e.target.value)}
              />
            </Labeled>
          </div>

          <fieldset className="space-y-4 rounded-lg border border-border bg-surface p-4">
            <legend className="px-1 text-xs font-medium tracking-wide text-text-muted uppercase">
              Check parameters
            </legend>
            {check === "account_balance_equals" && (
              <>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Labeled label="Account">
                    <Select
                      className="w-full"
                      value={p.account}
                      onChange={(e) => set({ account: e.target.value, mode: "amount" })}
                    >
                      <option value="seed">A seed account of the student</option>
                      <option value="opened">An account the student opened</option>
                    </Select>
                  </Labeled>
                  {p.account === "seed" ? (
                    <Labeled label="Seed account number" hint="0 = first seed account">
                      <TextInput
                        inputMode="numeric"
                        value={p.seed_index}
                        onChange={(e) => set({ seed_index: e.target.value })}
                      />
                    </Labeled>
                  ) : (
                    <Labeled label="Product" optional>
                      <Select
                        className="w-full"
                        value={p.product_code}
                        onChange={(e) => set({ product_code: e.target.value })}
                      >
                        <option value="">Any product</option>
                        {PRODUCT_CODES.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </Select>
                    </Labeled>
                  )}
                </div>
                <div className="grid gap-4 sm:grid-cols-3">
                  {p.account === "seed" && (
                    <Labeled label="Expected">
                      <Select
                        className="w-full"
                        value={p.mode}
                        onChange={(e) => set({ mode: e.target.value as P["mode"] })}
                      >
                        <option value="amount">Final balance</option>
                        <option value="delta">Change from opening</option>
                      </Select>
                    </Labeled>
                  )}
                  <Labeled label={p.mode === "delta" ? "Change (+/-)" : "Balance"}>
                    <TextInput
                      inputMode="decimal"
                      value={p.amount}
                      onChange={(e) => set({ amount: e.target.value })}
                    />
                  </Labeled>
                  <Labeled label="Currency" optional>
                    <CurrencySelect optional value={p.currency} onChange={(v) => set({ currency: v })} />
                  </Labeled>
                </div>
              </>
            )}
            {check === "txn_exists" && (
              <div className="grid gap-4 sm:grid-cols-2">
                <Labeled label="Transaction type" required>
                  <Select
                    className="w-full"
                    value={p.type}
                    onChange={(e) => set({ type: e.target.value })}
                  >
                    <option value="">Select…</option>
                    {TXN_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {TYPE_LABEL[t] ?? labelOf(t)}
                      </option>
                    ))}
                  </Select>
                </Labeled>
                <Labeled label="Minimum count" required>
                  <TextInput
                    inputMode="numeric"
                    value={p.min_count}
                    onChange={(e) => set({ min_count: e.target.value })}
                  />
                </Labeled>
                <Labeled label="Amount" required>
                  <TextInput
                    inputMode="decimal"
                    value={p.amount}
                    onChange={(e) => set({ amount: e.target.value })}
                  />
                </Labeled>
                <Labeled label="Currency" required>
                  <CurrencySelect value={p.currency} onChange={(v) => set({ currency: v })} />
                </Labeled>
              </div>
            )}
            {check === "till_closed_balanced" && (
              <Labeled label="Currency" optional hint="Leave empty to check every currency.">
                <CurrencySelect optional value={p.currency} onChange={(v) => set({ currency: v })} />
              </Labeled>
            )}
            {check === "customer_created" && (
              <div className="grid gap-4 sm:grid-cols-2">
                <Labeled label="Customer type" optional>
                  <Select
                    className="w-full"
                    value={p.type}
                    onChange={(e) => set({ type: e.target.value })}
                  >
                    <option value="">Any type</option>
                    {CUSTOMER_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t === "ngo" ? "NGO" : labelOf(t)}
                      </option>
                    ))}
                  </Select>
                </Labeled>
                <Labeled label="Minimum count" required>
                  <TextInput
                    inputMode="numeric"
                    value={p.min_count}
                    onChange={(e) => set({ min_count: e.target.value })}
                  />
                </Labeled>
              </div>
            )}
            {errs.params && <p className="text-sm text-fin-danger">{errs.params}</p>}
          </fieldset>

          <ErrorMsg error={error} />
          <DialogFooter>
            <Button type="button" variant="outline" disabled={pending} onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={pending}>
              {pending ? "Saving…" : task ? "Save task" : "Add task"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
