"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useSessionMe } from "@/lib/lab";
import { nextDate, useCloseDay, useEodStatus } from "@/lib/eod";
import { useRerun } from "@/lib/eod-rerun";
import { EmptyState } from "@/components/shared/empty-state";
import { LoadingSkeleton } from "@/components/shared/loading-skeleton";
import { ErrorMsg, QueryState, ReadOnlyBanner } from "@/components/lab/common";
import { EodHeader } from "@/components/eod/eod-header";
import { DateCard } from "@/components/eod/date-card";
import { ChecksCard } from "@/components/eod/checks-card";
import { SummaryCard } from "@/components/eod/summary-card";
import { CloseCard } from "@/components/eod/close-card";
import { RecentClosings } from "@/components/eod/recent-closings";
import { ClosedDialog, ConfirmCloseDialog } from "@/components/eod/close-dialogs";

export default function EndOfDayPage() {
  const { sessionId: sid } = useParams<{ sessionId: string }>();
  const router = useRouter();
  const me = useSessionMe(sid);
  const canRun = !!me.data?.permissions.some((p) => p.code === "eod.run");
  const readOnly = !!me.data?.read_only;
  const status = useEodStatus(sid, canRun);
  const close = useCloseDay(sid);
  const rerun = useRerun(status.refetch, status.data?.checks.length ?? 0);
  const [open, setOpen] = useState(false);
  const [done, setDone] = useState<{ closed: string; next: string } | null>(null);
  const d = status.data;

  function onConfirm() {
    close.mutate(undefined, {
      onSuccess: (r) => {
        setOpen(false);
        setDone({ closed: r.closed_date, next: r.business_date });
      },
      onError: () => setOpen(false),
    });
  }

  return (
    <div className="w-full space-y-4 p-6">
      <EodHeader
        updatedAt={status.dataUpdatedAt}
        busy={rerun.busy || status.isFetching}
        onRerun={rerun.rerun}
        showRerun={canRun && !!d}
      />
      <QueryState query={me}>
        {readOnly && <ReadOnlyBanner />}
        {!canRun ? (
          <EmptyState title="No access" description="Your role cannot run end of day." />
        ) : status.isPending ? (
          <LoadingSkeleton />
        ) : status.isError || !d ? (
          <ErrorMsg error={status.error} />
        ) : (
          <>
            <DateCard date={d.business_date} failed={d.checks.filter((c) => !c.ok).length} />
            {close.isError && <ErrorMsg error={close.error} />}
            <div className="grid items-start gap-4 lg:grid-cols-3">
              <div className="lg:col-span-2">
                <ChecksCard checks={d.checks} sid={sid} isRunning={rerun.isRunning} />
              </div>
              <div className="space-y-4">
                <SummaryCard summary={d.summary} />
                {!readOnly && (
                  <CloseCard
                    date={d.business_date}
                    canClose={d.can_close && !rerun.busy}
                    busy={close.isPending}
                    onClose={() => setOpen(true)}
                  />
                )}
                <RecentClosings items={d.recent_closings} />
              </div>
            </div>
            <ConfirmCloseDialog
              open={open}
              onOpenChange={setOpen}
              date={d.business_date}
              next={nextDate(d.business_date)}
              pending={close.isPending}
              onConfirm={onConfirm}
            />
          </>
        )}
      </QueryState>
      <ClosedDialog result={done} onDismiss={() => setDone(null)} onBack={() => router.push(`/s/${sid}`)} />
    </div>
  );
}
