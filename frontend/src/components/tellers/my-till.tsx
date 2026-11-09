"use client";

import { useState } from "react";
import { toast } from "sonner";
import { useSessionMe } from "@/lib/lab";
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
import { Balances, CountSummary } from "./session-bits";
import { PendingTransfers, TillStatusCard } from "./till-status-card";
import { Lock, XCircle } from "lucide-react";

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

function SessionBody({
  sid,
  s,
  readOnly,
}: {
  sid: string;
  s: TellerSession;
  readOnly: boolean;
}) {
  const act = useTellerAction(sid);
  const [counting, setCounting] = useState(false);
  const [confirmCancel, setConfirmCancel] = useState(false);

  return (
    <div className="space-y-5">
      <TillStatusCard s={s}>
        {s.status === "pending_open" && !readOnly && (
          <Button
            variant="outline"
            disabled={act.isPending}
            onClick={() => setConfirmCancel(true)}
            className="text-fin-danger"
          >
            <XCircle />
            Cancel request
          </Button>
        )}
        {s.status === "open" && !readOnly && !counting && (
          <Button onClick={() => setCounting(true)}>
            <Lock />
            Close till
          </Button>
        )}
      </TillStatusCard>

      {s.status === "pending_open" && (
        <>
          <PendingTransfers s={s} />
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
          <PendingTransfers s={s} />
          {counting && (
            <CloseCountForm sid={sid} s={s} onDone={() => setCounting(false)} />
          )}
        </>
      )}

      {s.status === "closing" && (
        <>
          <CountSummary counts={s.latest_counts} />
        </>
      )}

      {s.status === "closed" && (
        <>
          {s.close_approved_by_name && (
            <p className="text-sm text-text-muted">
              Closing approved by {s.close_approved_by_name}.
            </p>
          )}
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
        {!allowed ? (
          <EmptyState
            title="No access"
            description="Your role does not use a till."
          />
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
          <EmptyState
            title="No till session"
            description="No till was opened today."
          />
        ) : (
          <OpenRequestForm sid={sid} />
        )}
      </QueryState>
    </div>
  );
}
