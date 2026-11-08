"use client";

import { useState } from "react";
import { toast } from "sonner";
import { formatDateTime, useSessionMe } from "@/lib/lab";
import { formatMoney } from "@/lib/banking";
import { useTellerAction, useTellerSessions } from "@/lib/tellers";
import type { TellerSession } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { EmptyState } from "@/components/shared/empty-state";
import {
  Empty,
  ErrorMsg,
  Loading,
  PageHeader,
  QueryState,
  ReadOnlyBanner,
  Table,
  Td,
  Th,
} from "@/components/lab/common";
import { CountSummary, CURRENCIES, SessionStatus } from "./session-bits";

type Reject = { s: TellerSession; kind: "reject-open" | "reject-close" };

export function TillsOverview({ sid }: { sid: string }) {
  const me = useSessionMe(sid);
  const perms = new Set(me.data?.permissions.map((p) => p.code));
  const canOpen = perms.has("till.open.approve");
  const canClose = perms.has("till.close.approve");
  const allowed = canOpen || canClose;
  const list = useTellerSessions(sid, allowed);
  const act = useTellerAction(sid);
  const readOnly = !!me.data?.read_only;
  const [reject, setReject] = useState<Reject | null>(null);
  const [reason, setReason] = useState("");
  const [reasonErr, setReasonErr] = useState<string | null>(null);
  const [approveClose, setApproveClose] = useState<TellerSession | null>(null);

  function approveOpen(s: TellerSession) {
    act.mutate(
      { kind: "approve-open", id: s.id },
      {
        onSuccess: () => toast.success(`Till ${s.till_code} opened`),
        onError: (e) => toast.error(e.message),
      },
    );
  }

  function doApproveClose() {
    if (!approveClose) return;
    act.mutate(
      { kind: "approve-close", id: approveClose.id },
      {
        onSuccess: () => {
          toast.success("Till closed and cash returned to the vault");
          setApproveClose(null);
        },
        onError: (e) => {
          toast.error(e.message);
          setApproveClose(null);
        },
      },
    );
  }

  function doReject() {
    if (!reject) return;
    if (!reason.trim()) return setReasonErr("Enter a reason for rejecting");
    act.mutate(
      { kind: reject.kind, id: reject.s.id, reason: reason.trim() },
      {
        onSuccess: () => {
          toast.success("Rejected");
          setReject(null);
          setReason("");
        },
        onError: (e) => setReasonErr(e.message),
      },
    );
  }

  function openReject(s: TellerSession, kind: Reject["kind"]) {
    setReason("");
    setReasonErr(null);
    setReject({ s, kind });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Tills"
        subtitle="Every teller session of the open business day."
      />
      <QueryState query={me}>
        {readOnly && <ReadOnlyBanner />}
        {!allowed ? (
          <EmptyState title="No access" description="Your role cannot manage tills." />
        ) : list.isPending ? (
          <Loading label="Loading tills" />
        ) : list.isError ? (
          <ErrorMsg error={list.error} />
        ) : !list.data.length ? (
          <Empty>No teller sessions today.</Empty>
        ) : (
          <div className="space-y-6">
            <Table>
              <thead>
                <tr>
                  <Th>Teller</Th>
                  <Th>Till</Th>
                  <Th>Status</Th>
                  <Th>Balances</Th>
                  <Th>Over / short</Th>
                  <Th>{""}</Th>
                </tr>
              </thead>
              <tbody>
                {list.data.map((s) => (
                  <tr key={s.id} className="align-top hover:bg-hover">
                    <Td>
                      {s.teller_name ?? "—"}
                      <span className="block text-xs text-text-muted">
                        {formatDateTime(s.open_requested_at)}
                      </span>
                    </Td>
                    <Td className="font-mono text-xs">{s.till_code}</Td>
                    <Td>
                      <SessionStatus status={s.status} />
                    </Td>
                    <Td className="tabular-nums">
                      {CURRENCIES.map((c) => (
                        <span key={c} className="block">
                          {formatMoney(
                            s.balances.find((b) => b.currency === c)?.balance ?? "0",
                            c,
                          )}
                        </span>
                      ))}
                    </Td>
                    <Td className="tabular-nums">
                      {s.latest_counts.length
                        ? s.latest_counts.map((c) => (
                            <span key={c.id} className="block">
                              {Number(c.difference) > 0 ? "+" : ""}
                              {formatMoney(c.difference, c.currency)}
                            </span>
                          ))
                        : "—"}
                    </Td>
                    <Td>
                      {!readOnly && (
                        <div className="flex justify-end gap-2">
                          {s.status === "pending_open" && canOpen && (
                            <>
                              <Button
                                size="sm"
                                disabled={act.isPending}
                                onClick={() => approveOpen(s)}
                              >
                                Approve open
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={act.isPending}
                                onClick={() => openReject(s, "reject-open")}
                              >
                                Reject
                              </Button>
                            </>
                          )}
                          {s.status === "closing" && canClose && (
                            <>
                              <Button
                                size="sm"
                                disabled={act.isPending}
                                onClick={() => setApproveClose(s)}
                              >
                                Approve close
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={act.isPending}
                                onClick={() => openReject(s, "reject-close")}
                              >
                                Reject
                              </Button>
                            </>
                          )}
                        </div>
                      )}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
            {list.data
              .filter((s) => s.status === "closing")
              .map((s) => (
                <section key={s.id} className="space-y-2">
                  <h2 className="text-sm font-semibold text-text-strong">
                    Closing count: {s.teller_name} · {s.till_code}
                  </h2>
                  <CountSummary counts={s.latest_counts} />
                </section>
              ))}
          </div>
        )}
      </QueryState>
      <ConfirmDialog
        open={!!approveClose}
        onOpenChange={(o) => !o && setApproveClose(null)}
        title="Approve till closing"
        description="Any over or short amount is posted and all cash returns to the vault."
        confirmLabel="Approve close"
        pending={act.isPending}
        onConfirm={doApproveClose}
      />
      <ConfirmDialog
        open={!!reject}
        onOpenChange={(o) => !o && setReject(null)}
        title={
          reject?.kind === "reject-open"
            ? "Reject opening request"
            : "Reject closing count"
        }
        description={
          <span className="block space-y-3">
            <span className="block">
              {reject && `${reject.s.teller_name} · till ${reject.s.till_code}`}
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
        confirmLabel="Reject"
        destructive
        pending={act.isPending}
        onConfirm={doReject}
      />
    </div>
  );
}
