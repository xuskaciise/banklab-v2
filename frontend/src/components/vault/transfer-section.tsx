"use client";

import { useState } from "react";
import { Inbox, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import type { CashTransferOut } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ROW_GRID, TransferRow } from "./transfer-row";

const SIZES = [10, 25, 50];
const HEADS = ["Transfer", "Amount", "Requested", "Progress", "Status", ""];

/** One direction of cash movement with its own count, empty state and paging. */
export function TransferSection({
  title,
  icon: Icon,
  tone,
  rows,
  loading,
  empty,
  mineOf,
  busy,
  onApprove,
  onReject,
  onView,
}: {
  title: string;
  icon: LucideIcon;
  tone: "pending" | "success";
  rows: CashTransferOut[];
  loading: boolean;
  empty: string;
  mineOf: (t: CashTransferOut) => "approve-custodian" | "approve-manager" | null;
  busy: boolean;
  onApprove: (t: CashTransferOut) => void;
  onReject: (t: CashTransferOut) => void;
  onView: (t: CashTransferOut) => void;
}) {
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(10);
  const pages = Math.max(1, Math.ceil(rows.length / size));
  const p = Math.min(page, pages);
  const pageRows = rows.slice((p - 1) * size, p * size);

  return (
    <section className="rounded-xl border border-border bg-card shadow-xs">
      <div className="flex items-center gap-2.5 border-b border-border px-4 py-3">
        <span
          className={cn(
            "flex size-8 items-center justify-center rounded-lg",
            tone === "pending"
              ? "bg-fin-pending-bg text-fin-pending"
              : "bg-fin-success-bg text-fin-success-dark",
          )}
        >
          <Icon className="size-4" aria-hidden />
        </span>
        <h2 className="text-sm font-semibold text-text-strong">{title}</h2>
        <span className="rounded-full bg-hover px-2 py-0.5 text-xs font-medium text-text-body tabular-nums">
          {rows.length}
        </span>
      </div>

      {loading ? (
        <div className="space-y-2 p-4">
          {[0, 1].map((i) => (
            <Skeleton key={i} className="h-12 rounded-lg" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <p className="flex flex-col items-center gap-2 px-4 py-8 text-sm text-text-muted">
          <Inbox className="size-5" aria-hidden />
          {empty}
        </p>
      ) : (
        <>
          <div
            className={cn(
              "hidden border-b border-border bg-surface px-4 py-2 text-xs font-medium text-text-muted md:grid",
              ROW_GRID,
            )}
          >
            {HEADS.map((h, i) => (
              <span key={i} className={i === 1 ? "text-right" : ""}>
                {h}
              </span>
            ))}
          </div>
          <ul className="max-h-[26rem] divide-y divide-border overflow-y-auto max-md:space-y-2 max-md:divide-y-0 max-md:p-3">
            {pageRows.map((t) => (
              <TransferRow
                key={t.id}
                t={t}
                mine={mineOf(t)}
                busy={busy}
                onApprove={() => onApprove(t)}
                onReject={() => onReject(t)}
                onView={() => onView(t)}
              />
            ))}
          </ul>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-4 py-3 text-xs text-text-muted">
            <span>
              Showing {(p - 1) * size + 1}–{Math.min(rows.length, p * size)} of {rows.length}
            </span>
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2">
                Rows
                <Select
                  aria-label={`Rows per page, ${title}`}
                  value={size}
                  onChange={(e) => {
                    setSize(Number(e.target.value));
                    setPage(1);
                  }}
                  className="h-8 w-[5.5rem] py-0 pr-8 pl-2 text-xs"
                >
                  {SIZES.map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </Select>
              </label>
              <Button variant="outline" size="sm" disabled={p <= 1} onClick={() => setPage(p - 1)}>
                Previous
              </Button>
              <span className="tabular-nums">
                {p} / {pages}
              </span>
              <Button variant="outline" size="sm" disabled={p >= pages} onClick={() => setPage(p + 1)}>
                Next
              </Button>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
