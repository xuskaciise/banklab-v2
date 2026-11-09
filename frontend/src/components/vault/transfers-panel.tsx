"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";
import { ArrowDown, ArrowUp, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTransferAction } from "@/lib/banking";
import type { CashTransferOut } from "@/lib/api/types";
import { Input, Select } from "@/components/ui/input";
import { ErrorMsg } from "@/components/lab/common";
import { ApproveDialog, DetailsDialog, RejectDialog } from "./transfer-dialogs";
import { TransferSection } from "./transfer-section";
import { canReject, directionOf, myStep, type Tab } from "./vault-utils";

const TABS: { id: Tab; label: string }[] = [
  { id: "mine", label: "Pending my approval" },
  { id: "manager", label: "Pending manager" },
  { id: "posted", label: "Posted" },
  { id: "rejected", label: "Rejected" },
  { id: "all", label: "All" },
];

export function TransfersPanel({
  sid,
  rows,
  loading,
  error,
  has,
  readOnly,
}: {
  sid: string;
  rows: CashTransferOut[];
  loading: boolean;
  error: unknown;
  has: (c: string) => boolean;
  readOnly: boolean;
}) {
  const act = useTransferAction(sid);
  const [tab, setTab] = useState<Tab | null>(null);
  const [q, setQ] = useState("");
  const [cur, setCur] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [approving, setApproving] = useState<CashTransferOut | null>(null);
  const [rejecting, setRejecting] = useState<CashTransferOut | null>(null);
  const [viewing, setViewing] = useState<CashTransferOut | null>(null);
  const [reason, setReason] = useState("");
  const [reasonErr, setReasonErr] = useState<string | null>(null);

  const mineOf = (t: CashTransferOut) => (readOnly ? null : myStep(t, has));
  const inTab = (t: CashTransferOut, id: Tab) =>
    id === "mine"
      ? !!mineOf(t)
      : id === "manager"
        ? t.status === "custodian_approved"
        : id === "posted"
          ? t.status === "posted"
          : id === "rejected"
            ? t.status === "rejected"
            : true;
  const counts = Object.fromEntries(
    TABS.map((x) => [x.id, rows.filter((t) => inTab(t, x.id)).length]),
  ) as Record<Tab, number>;
  const active: Tab = tab ?? (counts.mine > 0 ? "mine" : "all");
  const currencies = Array.from(new Set(rows.map((t) => t.currency))).sort();

  const shown = useMemo(() => {
    const term = q.trim().toLowerCase();
    return rows.filter(
      (t) =>
        inTab(t, active) &&
        (!cur || t.currency === cur) &&
        (!from || t.created_at.slice(0, 10) >= from) &&
        (!to || t.created_at.slice(0, 10) <= to) &&
        (!term ||
          `${t.from_label} ${t.to_label} ${t.requested_by_name} ${t.amount}`
            .toLowerCase()
            .includes(term)),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, active, q, cur, from, to, readOnly]);
  const toVault = shown.filter((t) => directionOf(t) === "to_vault");
  // Vault -> till (and any till -> till rows) go in the first section.
  const toTill = shown.filter((t) => directionOf(t) !== "to_vault");
  const waiting = (xs: CashTransferOut[]) => xs.some((t) => mineOf(t));

  function run(
    t: CashTransferOut,
    action: "approve-custodian" | "approve-manager",
  ) {
    act.mutate(
      { id: t.id, action },
      {
        onSuccess: () => {
          toast.success(
            action === "approve-custodian"
              ? "Custodian approval recorded"
              : "Transfer approved and posted",
          );
          setApproving(null);
        },
        onError: (e) => toast.error(e.message),
      },
    );
  }

  function confirmReject() {
    if (!rejecting) return;
    if (!reason.trim())
      return setReasonErr("Enter a reason for rejecting this transfer");
    act.mutate(
      { id: rejecting.id, action: "reject", reason: reason.trim() },
      {
        onSuccess: () => {
          toast.success("Transfer rejected");
          setRejecting(null);
          setReason("");
        },
        onError: (e) => toast.error(e.message),
      },
    );
  }

  const openReject = (t: CashTransferOut) => {
    setReason("");
    setReasonErr(null);
    setViewing(null);
    setRejecting(t);
  };

  return (
    <div className="space-y-4">
      <section className="rounded-xl border border-border bg-card shadow-xs">
        <div className="space-y-3 p-4">
          <h2 className="text-sm font-semibold text-text-strong">
            Filter cash transfers
          </h2>
          <div
            role="tablist"
            aria-label="Transfer status"
            className="flex flex-wrap gap-1.5"
          >
            {TABS.map((x) => (
              <button
                key={x.id}
                type="button"
                role="tab"
                aria-selected={active === x.id}
                onClick={() => setTab(x.id)}
                className={cn(
                  "rounded-full border px-3 py-1 text-xs font-medium transition-colors outline-none focus-visible:ring-2 focus-visible:ring-bank-accent",
                  active === x.id
                    ? "border-bank-primary bg-bank-sky-light text-bank-primary"
                    : "border-border text-text-body hover:bg-hover",
                )}
              >
                {x.label} ({counts[x.id]})
              </button>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative min-w-40 flex-1 sm:max-w-xs">
              <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-text-muted" />
              <Input
                aria-label="Search transfers"
                placeholder="Search transfers…"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                className="h-9 pl-8 text-sm"
              />
            </div>
            <Select
              aria-label="Currency"
              value={cur}
              onChange={(e) => setCur(e.target.value)}
              className="h-9 w-40 text-sm"
            >
              <option value="">All currencies</option>
              {currencies.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </Select>
            <Input
              type="date"
              aria-label="From date"
              value={from}
              onChange={(e) => setFrom(e.target.value)}
              className="h-9 w-40 text-sm"
            />
            <Input
              type="date"
              aria-label="To date"
              value={to}
              onChange={(e) => setTo(e.target.value)}
              className="h-9 w-40 text-sm"
            />
          </div>
        </div>
      </section>

      {error ? <ErrorMsg error={error} /> : null}
      {(() => {
        const till = (
          <TransferSection
            key="till"
            title="Cash to tills"
            icon={ArrowUp}
            tone="pending"
            rows={toTill}
            loading={loading}
            empty="No cash sent to tills"
            mineOf={mineOf}
            busy={act.isPending}
            onApprove={setApproving}
            onReject={openReject}
            onView={setViewing}
          />
        );
        const vault = (
          <TransferSection
            key="vault"
            title="Cash returned to vault"
            icon={ArrowDown}
            tone="success"
            rows={toVault}
            loading={loading}
            empty="No cash returned to the vault"
            mineOf={mineOf}
            busy={act.isPending}
            onApprove={setApproving}
            onReject={openReject}
            onView={setViewing}
          />
        );
        return !waiting(toTill) && waiting(toVault)
          ? [vault, till]
          : [till, vault];
      })()}

      <ApproveDialog
        t={approving}
        step={approving ? (mineOf(approving) ?? "") : ""}
        pending={act.isPending}
        onClose={() => setApproving(null)}
        onConfirm={() => {
          const s = approving && mineOf(approving);
          if (approving && s) run(approving, s);
        }}
      />
      <RejectDialog
        t={rejecting}
        reason={reason}
        setReason={setReason}
        err={reasonErr}
        pending={act.isPending}
        onClose={() => setRejecting(null)}
        onConfirm={confirmReject}
      />
      <DetailsDialog
        t={viewing}
        canReject={!!viewing && !readOnly && canReject(viewing, has)}
        onReject={() => viewing && openReject(viewing)}
        onClose={() => setViewing(null)}
      />
    </div>
  );
}
