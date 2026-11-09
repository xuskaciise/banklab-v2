"use client";

import { useState } from "react";
import { toast } from "sonner";
import { formatDateTime, useSessionMe } from "@/lib/lab";
import { formatMoney } from "@/lib/banking";
import { useMyTellerSession, useTellerAction } from "@/lib/tellers";
import type { TellerSession } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { EmptyState } from "@/components/shared/empty-state";
import {
  ErrorMsg,
  Loading,
  PageHeader,
  QueryState,
  ReadOnlyBanner,
} from "@/components/lab/common";
import { CloseCountForm } from "./close-count-form";
import { OpenRequestForm } from "./open-request-form";
import { TillStats } from "./till-stats";
import { Balances, CountSummary, SessionStatus } from "./session-bits";

function Note({ title, text }: { title: string; text: string }) {
  return (
    <div
      role="alert"
      className="rounded-md bg-fin-danger-bg px-3 py-2 text-sm text-fin-danger"
    >
      <span className="font-medium">{title}:</span> {text}
    </div>
  );
}

function Pending({ s }: { s: TellerSession }) {
  if (!s.pending_transfers.length) return null;
  return (
    <section className="space-y-2">
      <h2 className="text-sm font-semibold text-text-strong">
        Pending cash transfers
      </h2>
      <ul className="divide-y divide-border rounded-xl border border-border bg-card text-sm">
        {s.pending_transfers.map((t) => (
          <li key={t.id} className="flex justify-between gap-3 px-4 py-2">
            <span className="text-text-muted">
              {t.direction === "vault_to_teller"
                ? "Vault → till"
                : "Till → vault"}{" "}
              · {t.status.replace(/_/g, " ")}
            </span>
            <span className="font-medium tabular-nums">
              {formatMoney(t.amount, t.currency)}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function SessionBody({ sid, s, readOnly }: { sid: string; s: TellerSession; readOnly: boolean }) {
  const act = useTellerAction(sid);
  const [counting, setCounting] = useState(false);
  const [confirmCancel, setConfirmCancel] = useState(false);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <span className="font-semibold text-text-strong">Till {s.till_code}</span>
        <SessionStatus status={s.status} />
        <span className="text-text-muted">
          Requested {formatDateTime(s.open_requested_at)}
          {s.opened_at && <> · Opened {formatDateTime(s.opened_at)}</>}
          {s.closed_at && <> · Closed {formatDateTime(s.closed_at)}</>}
        </span>
      </div>

      {s.status === "pending_open" && (
        <>
          <p className="text-sm text-text-muted">
            Waiting for a manager to approve opening this till.
          </p>
          <Pending s={s} />
          {!readOnly && (
            <Button
              variant="outline"
              disabled={act.isPending}
              onClick={() => setConfirmCancel(true)}
            >
              Cancel request
            </Button>
          )}
          <ConfirmDialog
            open={confirmCancel}
            onOpenChange={setConfirmCancel}
            title="Cancel opening request"
            description="The till becomes available again and any pending opening float is cancelled."
            confirmLabel="Cancel request"
            destructive
            pending={act.isPending}
            onConfirm={() =>
              act.mutate(
                { kind: "cancel", id: s.id },
                {
                  onSuccess: () => {
                    toast.success("Request cancelled");
                    setConfirmCancel(false);
                  },
                  onError: (e) => {
                    toast.error(e.message);
                    setConfirmCancel(false);
                  },
                },
              )
            }
          />
        </>
      )}

      {s.status === "open" && (
        <>
          {s.close_reject_note && (
            <Note title="Closing rejected" text={s.close_reject_note} />
          )}
          <Balances s={s} />
          <Pending s={s} />
          {counting ? (
            <CloseCountForm sid={sid} s={s} onDone={() => setCounting(false)} />
          ) : (
            !readOnly && (
              <Button onClick={() => setCounting(true)}>Close till</Button>
            )
          )}
        </>
      )}

      {s.status === "closing" && (
        <>
          <p className="text-sm text-text-muted">
            Your count was submitted. Waiting for a manager to approve closing.
          </p>
          <CountSummary counts={s.latest_counts} />
        </>
      )}

      {s.status === "closed" && (
        <>
          <p className="text-sm text-text-muted">
            This till is closed for the day. All cash was returned to the vault.
            {s.close_approved_by_name && ` Approved by ${s.close_approved_by_name}.`}
          </p>
          <CountSummary counts={s.latest_counts} />
        </>
      )}
    </div>
  );
}

export function MyTill({ sid }: { sid: string }) {
  const me = useSessionMe(sid);
  const perms = new Set(me.data?.permissions.map((p) => p.code));
  const allowed = perms.has("till.open.request") || perms.has("till.close");
  const mine = useMyTellerSession(sid, allowed);
  const readOnly = !!me.data?.read_only;
  const s = mine.data;

  return (
    <div className="space-y-6">
      <PageHeader
        title="My Till"
        subtitle="Manage your teller till, request opening funds, and close your till at the end of the business day."
      />
      <QueryState query={me}>
        {readOnly && <ReadOnlyBanner />}
        {allowed && <TillStats sid={sid} />}
        {!allowed ? (
          <EmptyState title="No access" description="Your role does not use a till." />
        ) : mine.isPending ? (
          <Loading label="Loading till" />
        ) : mine.isError ? (
          <ErrorMsg error={mine.error} />
        ) : s ? (
          <>
            {s.open_reject_note && s.status === "pending_open" && (
              <Note title="Previous note" text={s.open_reject_note} />
            )}
            <SessionBody sid={sid} s={s} readOnly={readOnly} />
          </>
        ) : readOnly ? (
          <EmptyState title="No till session" description="No till was opened today." />
        ) : (
          <OpenRequestForm sid={sid} />
        )}
      </QueryState>
    </div>
  );
}
