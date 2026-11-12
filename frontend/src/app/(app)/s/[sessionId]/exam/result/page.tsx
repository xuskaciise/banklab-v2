"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Check, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader, QueryState } from "@/components/lab/common";
import { fmtPoints, useMyExamResult } from "@/lib/exams";

export default function ExamResultPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const q = useMyExamResult(sessionId, true);
  const back = (
    <Button variant="outline" nativeButton={false} render={<Link href={`/s/${sessionId}/exam`} />}>
      Back to exam
    </Button>
  );
  const notReady = q.isError && (q.error as { status?: number }).status === 409;
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="My exam result" actions={back} />
      {notReady ? (
        <EmptyState
          title="Result not available yet"
          description="Your result appears here once you have submitted and your instructor has published the results."
        />
      ) : (
        <QueryState query={q}>
          {q.data && (
            <div className="space-y-6">
              <div className="rounded-xl border border-border bg-card p-6 text-center shadow-xs">
                <p className="text-sm text-text-muted">Your score</p>
                <p className="mt-1 text-4xl font-semibold tracking-tight text-text-strong tabular-nums">
                  {fmtPoints(q.data.score)}{" "}
                  <span className="text-xl font-normal text-text-muted">/ {fmtPoints(q.data.max_score)}</span>
                </p>
              </div>
              <ul className="divide-y divide-border rounded-xl border border-border bg-card shadow-xs">
                {q.data.tasks.map((t) => (
                  <li key={t.task_id} className="flex items-center gap-3 px-4 py-3">
                    <span
                      className={`flex size-6 shrink-0 items-center justify-center rounded-full ${t.passed ? "bg-fin-success-bg text-fin-success-dark" : "bg-fin-danger-bg text-fin-danger"}`}
                    >
                      {t.passed ? <Check className="size-4" /> : <X className="size-4" />}
                      <span className="sr-only">{t.passed ? "Passed" : "Not passed"}</span>
                    </span>
                    <span className="min-w-0 flex-1 text-text-strong">
                      {t.title}
                      {t.adjusted && <span className="ml-2 text-xs text-text-muted">(adjusted by instructor)</span>}
                    </span>
                    <span className="text-sm font-medium text-text-strong tabular-nums">
                      {fmtPoints(t.points)} / {fmtPoints(t.max_points)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </QueryState>
      )}
    </div>
  );
}
