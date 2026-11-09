"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { toast } from "sonner";
import { CalendarCheck } from "lucide-react";
import { useSessionMe } from "@/lib/lab";
import { nextDate, useCloseDay, useEodStatus } from "@/lib/eod";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { EmptyState } from "@/components/shared/empty-state";
import { LoadingSkeleton } from "@/components/shared/loading-skeleton";
import { ErrorMsg, QueryState, ReadOnlyBanner } from "@/components/lab/common";
import { CheckCard } from "@/components/eod/check-card";

export default function EndOfDayPage() {
  const { sessionId: sid } = useParams<{ sessionId: string }>();
  const me = useSessionMe(sid);
  const canRun = !!me.data?.permissions.some((p) => p.code === "eod.run");
  const readOnly = !!me.data?.read_only;
  const status = useEodStatus(sid, canRun);
  const close = useCloseDay(sid);
  const [open, setOpen] = useState(false);
  const [newDate, setNewDate] = useState<string | null>(null);
  const date = status.data?.business_date;

  function onConfirm() {
    close.mutate(undefined, {
      onSuccess: (r) => {
        setOpen(false);
        setNewDate(r.business_date);
        toast.success(`Business day ${r.closed_date} closed. New business date: ${r.business_date}`);
      },
      onError: () => setOpen(false),
    });
  }

  return (
    <div className="w-full max-w-3xl space-y-4 p-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-text-strong sm:text-2xl">End of day</h1>
        <p className="mt-0.5 text-sm text-text-muted">
          Run the closing checks, then close the business day and open the next one.
        </p>
      </div>
      <QueryState query={me}>
        {readOnly && <ReadOnlyBanner />}
        {!canRun ? (
          <EmptyState title="No access" description="Your role cannot run end of day." />
        ) : status.isPending ? (
          <LoadingSkeleton />
        ) : status.isError ? (
          <ErrorMsg error={status.error} />
        ) : (
          <>
            <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-border bg-card p-4">
              <div className="flex items-center gap-3">
                <CalendarCheck className="size-8 text-bank-primary" aria-hidden />
                <div>
                  <p className="text-xs font-medium tracking-wider text-text-muted uppercase">
                    Current business date
                  </p>
                  <p className="text-2xl font-semibold text-text-strong tabular-nums">{date}</p>
                  {newDate && newDate === date && (
                    <p className="text-xs text-fin-success-dark">Day closed. This is the new business date.</p>
                  )}
                </div>
              </div>
              {!readOnly && (
                <Button disabled={!status.data.can_close || close.isPending} onClick={() => setOpen(true)}>
                  Close day
                </Button>
              )}
            </div>
            {close.isError && <ErrorMsg error={close.error} />}
            <ul className="space-y-3">
              {status.data.checks.map((c) => (
                <CheckCard key={c.code} check={c} sid={sid} />
              ))}
            </ul>
            {date && (
              <ConfirmDialog
                open={open}
                onOpenChange={setOpen}
                title="Close business day"
                description={`Close business day ${date} and open ${nextDate(date)}?`}
                confirmLabel="Close day"
                pending={close.isPending}
                onConfirm={onConfirm}
              />
            )}
          </>
        )}
      </QueryState>
    </div>
  );
}
