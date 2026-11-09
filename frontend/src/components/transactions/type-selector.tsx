"use client";

import { ArrowDownToLine, ArrowLeftRight, ArrowUpFromLine } from "lucide-react";
import { OptionCards } from "@/components/shared/form-layout";

export type Kind = "deposit" | "withdrawal" | "transfer";

export const KIND_META: Record<
  Kind,
  { label: string; hint: string; icon: typeof ArrowDownToLine }
> = {
  deposit: {
    label: "Cash Deposit",
    hint: "Add funds to a customer account.",
    icon: ArrowDownToLine,
  },
  withdrawal: {
    label: "Cash Withdrawal",
    hint: "Withdraw funds from an account.",
    icon: ArrowUpFromLine,
  },
  transfer: {
    label: "Account Transfer",
    hint: "Transfer funds between accounts.",
    icon: ArrowLeftRight,
  },
};

/** Radio-group of transaction types (shared OptionCards). */
export function TypeSelector({
  kinds,
  value,
  onChange,
}: {
  kinds: Kind[];
  value: Kind;
  onChange: (k: Kind) => void;
}) {
  return (
    <OptionCards
      label="Transaction type"
      options={kinds.map((k) => ({ value: k, ...KIND_META[k] }))}
      value={value}
      onChange={onChange}
    />
  );
}
