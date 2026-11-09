"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";
import { Inbox, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTransferAction } from "@/lib/banking";
import type { CashTransferOut } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorMsg } from "@/components/lab/common";
import { ApproveDialog, DetailsDialog, RejectDialog } from "./transfer-dialogs";
import { ROW_GRID, TransferRow } from "./transfer-row";
import { canReject, directionOf, myStep, type Tab } from "./vault-utils";

const TABS: { id: Tab; label: string }[] = [
  { id: "mine", label: "Pending my approval" },
  { id: "manager", label: "Pending manager" },
  { id: "posted", label: "Posted" },
  { id: "rejected", label: "Rejected" },
  { id: "all", label: "All" },
];
const SIZES = [10, 25, 50];
const HEADS = ["Direction", "Transfer", "Amount", "Requested", "Progress", "Status", ""];

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
  const [dir, setDir] = useState("");
  const [cur, setCur] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(10);
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
        (!dir || directionOf(t) === dir) &&
        (!cur || t.currency === cur) &&
        (!from || t.created_at.slice(0, 10) >= from) &&
        (!to || t.created_at.slice(0, 10) <= to) &&
        (!term ||
          `${t.from_label} ${t.to_label} ${t.requested_by_name} ${t.amount}`
            .toLowerCase()
            .includes(term)),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, active, q, dir, cur, from, to, readOnly]);
  const pages = Math.max(1, Math.ceil(shown.length / size));
  const p = Math.min(page, pages);
  const pageRows = shown.slice((p - 1) * size, p * size);
  const reset = <T,>(set: (v: T) => void) => (v: T) => {
    set(v);
    setPage(1);
  };

  function run(t: CashTransferOut, action: "approve-custodian" | "approve-manager") {
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
    if (!reason.trim()) return setReasonErr("Enter a reason for rejecting this transfer");
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
    <section className="rounded-xl border border-border bg-card shadow-xs">
      <div className="space-y-3 border-b border-border p-4">
        <h2 className="text-sm font-semibold text-text-strong">Cash transfers</h2>
        <div role="tablist" aria-label="Transfer status" className="flex flex-wrap gap-1.5">
          {TABS.map((x) => (
            <button
              key={x.id}
              type="button"
              role="tab"
              aria-selected={active === x.id}
              onClick={() => reset(setTab)(x.id)}
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
            <Input aria-label="Search transfers" placeholder="Search transfers…" value={q}
              onChange={(e) => reset(setQ)(e.target.value)} className="h-9 pl-8 text-sm" />
          </div>
          <Select aria-label="Direction" value={dir} onChange={(e) => reset(setDir)(e.target.value)} className="h-9 w-36 text-sm">
            <option value="">All directions</option>
            <option value="to_till">To till</option>
            <option value="to_vault">To vault</option>
          </Select>
          <Select aria-label="Currency" value={cur} onChange={(e) => reset(setCur)(e.target.value)} className="h-9 w-32 text-sm">
            <option value="">All currencies</option>
            {currencies.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </Select>
          <Input type="date" aria-label="From date" value={from} onChange={(e) => reset(setFrom)(e.target.value)} className="h-9 w-40 text-sm" />
          <Input type="date" aria-label="To date" value={to} onChange={(e) => reset(setTo)(e.target.value)} className="h-9 w-40 text-sm" />
        </div>
      </div>

      {error ? (
        <div className="p-4"><ErrorMsg error={error} /></div>
      ) : loading ? (
        <div className="space-y-2 p-4">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-12 rounded-lg" />)}
        </div>
      ) : shown.length === 0 ? (
        <p className="flex flex-col items-center gap-2 px-4 py-12 text-sm text-text-muted">
          <Inbox className="size-6" aria-hidden />
          {active === "mine" ? "Nothing is waiting for your approval." : "No transfers in this view."}
        </p>
      ) : (
        <>
          <div className={cn("hidden border-b border-border bg-surface px-4 py-2 text-xs font-medium text-text-muted md:grid", ROW_GRID)}>
            {HEADS.map((h, i) => (
              <span key={i} className={i === 2 ? "text-right" : ""}>{h}</span>
            ))}
          </div>
          <ul className="max-h-[32rem] divide-y divide-border overflow-y-auto max-md:space-y-2 max-md:divide-y-0 max-md:p-3">
            {pageRows.map((t) => (
              <TransferRow
                key={t.id}
                t={t}
                mine={mineOf(t)}
                busy={act.isPending}
                onApprove={() => setApproving(t)}
                onReject={() => openReject(t)}
                onView={() => setViewing(t)}
              />
            ))}
          </ul>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-4 py-3 text-xs text-text-muted">
            <span>
              Showing {(p - 1) * size + 1}–{Math.min(shown.length, p * size)} of {shown.length}
            </span>
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2">
                Rows
                <Select aria-label="Rows per page" value={size}
                  onChange={(e) => { setSize(Number(e.target.value)); setPage(1); }}
                  className="h-8 w-[5.5rem] py-0 pr-8 pl-2 text-xs">
                  {SIZES.map((n) => <option key={n} value={n}>{n}</option>)}
                </Select>
              </label>
              <Button variant="outline" size="sm" disabled={p <= 1} onClick={() => setPage(p - 1)}>Previous</Button>
              <span className="tabular-nums">{p} / {pages}</span>
              <Button variant="outline" size="sm" disabled={p >= pages} onClick={() => setPage(p + 1)}>Next</Button>
            </div>
          </div>
        </>
      )}

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
    </section>
  );
}
