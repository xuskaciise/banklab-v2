"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import type { ColumnDef } from "@tanstack/react-table";
import { toast } from "sonner";
import { Landmark } from "lucide-react";
import { formatDateTime, useSessionMe } from "@/lib/lab";
import {
  formatMoney,
  useCashTransfers,
  useTransferAction,
  useVault,
} from "@/lib/banking";
import type { CashTransferOut, VaultOut } from "@/lib/api/types";
import { useTellerSessions } from "@/lib/tellers";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { DataTable } from "@/components/shared/data-table";
import { EmptyState } from "@/components/shared/empty-state";
import { StatCard } from "@/components/shared/stat-card";
import { StatusBadge } from "@/components/shared/status-badge";
import {
  ErrorMsg,
  Loading,
  PageHeader,
  QueryState,
  ReadOnlyBanner,
} from "@/components/lab/common";

const CURRENCIES = ["USD", "SOS"] as const;

const STATUS_LABEL: Record<string, string> = {
  pending: "Awaiting custodian",
  custodian_approved: "Awaiting manager",
  posted: "Posted",
  rejected: "Rejected",
  cancelled: "Cancelled",
};

function Recon({
  label,
  left,
  right,
  ok,
  currency,
}: {
  label: string;
  left: number | string;
  right: number | string;
  ok: boolean;
  currency: string;
}) {
  return (
    <span className="flex flex-wrap items-center justify-between gap-2 text-xs">
      <span className="text-text-muted">
        {label} {formatMoney(left, currency)} vs GL{" "}
        {formatMoney(right, currency)}
      </span>
      <StatusBadge
        status={ok ? "ok" : "mismatch"}
        label={ok ? "Reconciled" : "Mismatch"}
        tone={ok ? "success" : "danger"}
      />
    </span>
  );
}

function Positions({ vault }: { vault: VaultOut }) {
  if (!vault.branches.length)
    return (
      <EmptyState
        icon={Landmark}
        title="No branches yet"
        description="Your instructor has not set up a branch for this bank."
      />
    );
  return (
    <div className="space-y-6">
      {vault.branches.map((b) => (
        <section key={b.branch_id} className="space-y-3">
          <h2 className="text-sm font-semibold text-text-strong">
            {b.branch_name}{" "}
            <span className="font-mono text-xs font-normal text-text-muted">
              {b.branch_code}
            </span>
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {CURRENCIES.map((c) => {
              const pos = b.positions.find((p) => p.currency === c);
              return (
                <StatCard
                  key={c}
                  label={`Vault cash ${c}`}
                  icon={Landmark}
                  value={
                    <span className="text-2xl">
                      {formatMoney(pos?.balance ?? "0", c)}
                    </span>
                  }
                />
              );
            })}
          </div>
        </section>
      ))}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-text-strong">
          GL reconciliation{" "}
          <span className="text-xs font-normal text-text-muted">
            (whole bank)
          </span>
        </h2>
        <div className="grid gap-4 sm:grid-cols-2">
          {CURRENCIES.map((c) => {
            const rec = vault.reconciliation.find((r) => r.currency === c);
            if (!rec) return null;
            return (
              <div
                key={c}
                className="space-y-1.5 rounded-lg border border-border bg-surface p-4"
              >
                <Recon
                  label="All vaults"
                  left={rec.vault_total}
                  right={rec.gl_vault}
                  ok={rec.vault_total === rec.gl_vault}
                  currency={c}
                />
                <Recon
                  label="All tills"
                  left={rec.teller_total}
                  right={rec.gl_teller}
                  ok={rec.teller_total === rec.gl_teller}
                  currency={c}
                />
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}

export default function VaultPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const me = useSessionMe(sessionId);
  const perms = new Set(me.data?.permissions.map((p) => p.code));
  const canView = perms.has("vault.view");
  const vault = useVault(sessionId, canView);
  const transfers = useCashTransfers(sessionId, canView);
  const act = useTransferAction(sessionId);
  const [rejecting, setRejecting] = useState<CashTransferOut | null>(null);
  const [reason, setReason] = useState("");
  const [reasonErr, setReasonErr] = useState<string | null>(null);
  const readOnly = !!me.data?.read_only;

  function run(
    t: CashTransferOut,
    action: "approve-custodian" | "approve-manager",
  ) {
    act.mutate(
      { id: t.id, action },
      {
        onSuccess: () =>
          toast.success(
            action === "approve-custodian"
              ? "Custodian approval recorded"
              : "Transfer approved and posted",
          ),
        onError: (e) => toast.error(e.message),
      },
    );
  }

  function confirmReject() {
    if (!rejecting) return;
    if (!reason.trim()) {
      setReasonErr("Enter a reason for rejecting this transfer");
      return;
    }
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

  const tellerSessions = useTellerSessions(
    sessionId,
    perms.has("till.open.approve") || perms.has("till.close.approve"),
  );
  const branchByVault = new Map(
    vault.data?.branches.map((b) => [b.vault_id, b.branch_name]) ?? [],
  );
  const tillBySession = new Map(
    (tellerSessions.data ?? []).map((ts) => [
      ts.id,
      `Till ${ts.till_code}${ts.teller_name ? ` · ${ts.teller_name}` : ""}`,
    ]),
  );
  const holder = (type: string, id: string) =>
    type === "vault"
      ? `Vault${branchByVault.get(id) ? ` (${branchByVault.get(id)})` : ""}`
      : type === "teller_session"
        ? (tillBySession.get(id) ?? "Teller till")
        : type.replace(/_/g, " ");

  const columns: ColumnDef<CashTransferOut>[] = [
    {
      accessorKey: "created_at",
      header: "Transfer",
      cell: ({ row: { original: t } }) => (
        <div className="min-w-0">
          <p className="font-medium text-text-strong">
            {holder(t.from_type, t.from_id)} → {holder(t.to_type, t.to_id)}
          </p>
          <p className="text-xs text-text-muted tabular-nums">
            {formatDateTime(t.created_at)} · by {t.requested_by_name}
          </p>
        </div>
      ),
    },
    {
      accessorKey: "amount",
      header: () => <span className="block text-right">Amount</span>,
      cell: ({ row: { original: t } }) => (
        <span className="block text-right font-semibold whitespace-nowrap text-text-strong tabular-nums">
          {formatMoney(t.amount, t.currency)}
        </span>
      ),
    },
    {
      accessorKey: "status",
      header: "Status",
      cell: ({ row: { original: t } }) => (
        <div className="space-y-1">
          <StatusBadge
            status={t.status === "custodian_approved" ? "pending" : t.status}
            label={STATUS_LABEL[t.status] ?? t.status}
          />
          {(t.approved_by_1_name ||
            t.approved_by_2_name ||
            (t.status === "rejected" && t.reason)) && (
            <p className="text-xs text-text-muted">
              {t.approved_by_1_name && <>1st: {t.approved_by_1_name}</>}
              {t.approved_by_2_name && <> · 2nd: {t.approved_by_2_name}</>}
              {t.status === "rejected" && t.reason && <> · {t.reason}</>}
            </p>
          )}
        </div>
      ),
    },
    {
      id: "actions",
      header: "",
      enableSorting: false,
      cell: ({ row: { original: t } }) => {
        if (readOnly) return null;
        const canCustodian =
          t.status === "pending" && perms.has("cash.vault.approve_custodian");
        const canManager =
          t.status === "custodian_approved" &&
          perms.has("cash.vault.approve_manager");
        const canReject =
          (t.status === "pending" || t.status === "custodian_approved") &&
          (perms.has("cash.vault.approve_custodian") ||
            perms.has("cash.vault.approve_manager"));
        if (!canCustodian && !canManager && !canReject) return null;
        return (
          <div className="flex flex-wrap justify-end gap-2">
            {canCustodian && (
              <Button
                size="sm"
                disabled={act.isPending}
                onClick={() => run(t, "approve-custodian")}
              >
                Approve
              </Button>
            )}
            {canManager && (
              <Button
                size="sm"
                disabled={act.isPending}
                onClick={() => run(t, "approve-manager")}
              >
                Approve
              </Button>
            )}
            {canReject && (
              <Button
                size="sm"
                variant="outline"
                disabled={act.isPending}
                onClick={() => {
                  setReason("");
                  setReasonErr(null);
                  setRejecting(t);
                }}
              >
                Reject
              </Button>
            )}
          </div>
        );
      },
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Vault"
        subtitle="Branch cash positions, reconciliation with the general ledger and dual-control cash transfers."
      />
      <QueryState query={me}>
        {readOnly && <ReadOnlyBanner />}
        {!canView ? (
          <EmptyState
            title="No access"
            description="Your role cannot view the vault."
          />
        ) : (
          <>
            {vault.isPending ? (
              <Loading label="Loading vault" />
            ) : vault.isError ? (
              <ErrorMsg error={vault.error} />
            ) : (
              <Positions vault={vault.data} />
            )}
            <section className="space-y-3">
              <h2 className="text-sm font-semibold text-text-strong">
                Cash transfers
              </h2>
              <DataTable
                columns={columns}
                data={transfers.data}
                isLoading={transfers.isPending}
                error={transfers.error}
                getRowId={(t) => t.id}
                searchPlaceholder="Search transfers…"
                columnToggle={false}
                initialSort={[{ id: "created_at", desc: true }]}
                fit
                emptyTitle="No cash transfers"
                emptyDescription="Cash transfers between the vault and tills will appear here for approval."
              />
            </section>
          </>
        )}
      </QueryState>
      <ConfirmDialog
        open={!!rejecting}
        onOpenChange={(o) => !o && setRejecting(null)}
        title="Reject cash transfer"
        description={
          <span className="block space-y-3">
            <span className="block">
              {rejecting &&
                `${formatMoney(rejecting.amount, rejecting.currency)} requested by ${rejecting.requested_by_name}.`}
            </span>
            <Textarea
              aria-label="Reason"
              placeholder="Reason for rejection"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
            {reasonErr && (
              <span className="block text-sm text-fin-danger">{reasonErr}</span>
            )}
          </span>
        }
        confirmLabel="Reject transfer"
        destructive
        pending={act.isPending}
        onConfirm={confirmReject}
      />
    </div>
  );
}
