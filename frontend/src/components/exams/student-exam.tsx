"use client";

import { useState } from "react";
import Link from "next/link";
import { Check, Clock, X } from "lucide-react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorMsg, errorText, StatusBadge } from "@/components/lab/common";
import type { StudentExam } from "@/lib/api/types";
import {
  fmtCountdown,
  fmtPoints,
  useCountdown,
  useStartExam,
  useSubmitExam,
} from "@/lib/exams";
import { formatDateTime } from "@/lib/lab";
import { cn } from "@/lib/utils";

function Instructions({ text }: { text: string }) {
  if (!text.trim()) return null;
  return (
    <section className="rounded-xl border border-border bg-card p-5 shadow-xs">
      <h2 className="mb-2 text-base font-semibold text-text-strong">Instructions</h2>
      <p className="text-sm whitespace-pre-wrap text-text-body">{text}</p>
    </section>
  );
}

function Tasks({ exam, ticks }: { exam: StudentExam; ticks: boolean }) {
  const tasks = [...exam.tasks].sort((a, b) => a.position - b.position);
  if (!tasks.length) return null;
  return (
    <section className="rounded-xl border border-border bg-card shadow-xs">
      <h2 className="border-b border-border px-5 py-3 text-base font-semibold text-text-strong">
        Tasks
      </h2>
      <ol className="divide-y divide-border">
        {tasks.map((t, i) => {
          const marked = ticks && t.passed != null;
          return (
            <li key={t.id} className="flex items-start gap-3 px-5 py-3">
              <span
                className={cn(
                  "mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                  marked && t.passed && "bg-fin-success-bg text-fin-success-dark",
                  marked && !t.passed && "bg-fin-danger-bg text-fin-danger",
                  !marked && "bg-bank-sky-light text-bank-primary",
                )}
              >
                {marked ? t.passed ? <Check className="size-4" /> : <X className="size-4" /> : i + 1}
                {marked && <span className="sr-only">{t.passed ? "Done" : "Not done"}</span>}
              </span>
              <div className="min-w-0 flex-1">
                <p className="font-medium text-text-strong">{t.title}</p>
                {t.instructions && (
                  <p className="mt-0.5 text-sm whitespace-pre-wrap text-text-body">{t.instructions}</p>
                )}
              </div>
              <span className="text-xs whitespace-nowrap text-text-muted tabular-nums">
                {fmtPoints(t.points)} pts
              </span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function Running({ sid, exam }: { sid: string; exam: StudentExam }) {
  const qc = useQueryClient();
  const submit = useSubmitExam(sid);
  const [confirm, setConfirm] = useState(false);
  const left = useCountdown(exam.remaining_seconds, () => {
    qc.invalidateQueries({ queryKey: ["student-exam", sid] });
    qc.invalidateQueries({ queryKey: ["session-me", sid] });
  });
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card p-4 shadow-xs">
        <div className="flex items-center gap-2 text-text-strong">
          <Clock className="size-5 text-bank-primary" />
          <span className="text-sm text-text-muted">Time left</span>
          <span
            className={cn(
              "text-2xl font-semibold tabular-nums",
              left !== null && left <= 300 && "text-fin-danger",
            )}
          >
            {left === null ? "—" : fmtCountdown(left)}
          </span>
        </div>
        <Button onClick={() => setConfirm(true)}>Submit exam</Button>
      </div>
      <Instructions text={exam.instructions} />
      <Tasks exam={exam} ticks={false} />
      <p className="text-sm text-text-muted">
        Do the work in the normal screens (customers, accounts, transactions), then submit.
      </p>
      <ErrorMsg error={submit.error} />
      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title="Submit exam?"
        description="You cannot change anything after submitting."
        confirmLabel="Submit"
        pending={submit.isPending}
        onConfirm={() =>
          submit.mutate(undefined, {
            onSuccess: () => {
              setConfirm(false);
              toast.success("Exam submitted");
            },
            onError: () => setConfirm(false),
          })
        }
      />
    </div>
  );
}

export function StudentExamView({ sid, exam }: { sid: string; exam: StudentExam }) {
  const start = useStartExam(sid);
  switch (exam.state) {
    case "not_open":
      return (
        <EmptyState
          icon={Clock}
          title="The exam is not open yet"
          description={`It opens on ${formatDateTime(exam.starts_at)}.`}
        />
      );
    case "ready":
      return (
        <div className="space-y-4">
          <Instructions text={exam.instructions} />
          <div className="rounded-xl border border-border bg-card p-5 shadow-xs">
            <p className="text-sm text-text-body">
              You have <span className="font-semibold">{exam.duration_minutes} minutes</span> once you press
              Start, and the exam closes on {formatDateTime(exam.ends_at)}.
            </p>
            <ErrorMsg error={start.error} />
            <Button
              className="mt-4"
              disabled={start.isPending}
              onClick={() => start.mutate(undefined, { onError: (e) => toast.error(errorText(e)) })}
            >
              {start.isPending ? "Starting…" : "Start exam"}
            </Button>
          </div>
        </div>
      );
    case "in_progress":
      return <Running sid={sid} exam={exam} />;
    default: {
      const missed = exam.state === "missed";
      return (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card p-4 shadow-xs">
            <div className="space-y-1 text-sm">
              <StatusBadge status={missed ? "missed" : "submitted"} tone={missed ? "danger" : "success"} />
              <p className="text-text-muted">
                {missed
                  ? "The exam closed before you started it."
                  : `Submitted ${formatDateTime(exam.submitted_at)}${exam.auto_submitted ? " (automatically, time ran out)" : ""}.`}
              </p>
            </div>
            {!missed &&
              (exam.results_published ? (
                <Button nativeButton={false} render={<Link href={`/s/${sid}/exam/result`} />}>View my result</Button>
              ) : (
                <span className="text-sm text-text-muted">Results are not published yet.</span>
              ))}
          </div>
          {!missed && <Tasks exam={exam} ticks />}
        </div>
      );
    }
  }
}
