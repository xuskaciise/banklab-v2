import type { CashTransferOut } from "@/lib/api/types";

export type Tab = "mine" | "manager" | "posted" | "rejected" | "all";

export const titleCase = (s: string) =>
  s
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());

export const fmtWhen = (iso: string) =>
  new Date(iso).toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

export type Direction = "to_till" | "to_vault" | "other";
export const directionOf = (t: CashTransferOut): Direction =>
  t.from_type === "vault" ? "to_till" : t.to_type === "vault" ? "to_vault" : "other";

export const STATUS_LABEL: Record<string, string> = {
  pending: "Awaiting custodian",
  custodian_approved: "Awaiting manager",
  posted: "Posted",
  rejected: "Rejected",
  cancelled: "Cancelled",
};

export type Step = { label: string; by?: string | null; done: boolean };

/** Requested -> Custodian -> Manager -> Posted, from the row's own fields. */
export function stepsOf(t: CashTransferOut): Step[] {
  return [
    { label: "Requested", by: t.requested_by_name, done: true },
    { label: "Custodian", by: t.approved_by_1_name, done: !!t.approved_by_1_id },
    { label: "Manager", by: t.approved_by_2_name, done: !!t.approved_by_2_id },
    { label: "Posted", done: t.status === "posted" },
  ];
}

/** Which approval step this user may take on the row, if any. */
export function myStep(
  t: CashTransferOut,
  has: (c: string) => boolean,
): "approve-custodian" | "approve-manager" | null {
  if (t.status === "pending" && has("cash.vault.approve_custodian"))
    return "approve-custodian";
  if (t.status === "custodian_approved" && has("cash.vault.approve_manager"))
    return "approve-manager";
  return null;
}

export const canReject = (t: CashTransferOut, has: (c: string) => boolean) =>
  (t.status === "pending" || t.status === "custodian_approved") &&
  (has("cash.vault.approve_custodian") || has("cash.vault.approve_manager"));
