"use client";

import Link from "next/link";
import { Clock } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import type { ExamClock } from "@/lib/api/types";
import { fmtCountdown, useCountdown } from "@/lib/exams";
import { cn } from "@/lib/utils";

const STATE_LABEL: Record<string, string> = {
  not_open: "Exam not open",
  ready: "Exam ready",
  submitted: "Exam submitted",
  missed: "Exam missed",
};

/** Top-bar exam clock: server remaining_seconds, ticked locally. */
export function ExamClockBadge({
  sessionId,
  exam,
}: {
  sessionId: string;
  exam: ExamClock;
}) {
  const qc = useQueryClient();
  const running = exam.state === "in_progress";
  const left = useCountdown(running ? exam.remaining_seconds : null, () => {
    qc.invalidateQueries({ queryKey: ["session-me", sessionId] });
    qc.invalidateQueries({ queryKey: ["student-exam", sessionId] });
  });
  return (
    <Link
      href={`/s/${sessionId}/exam`}
      className={cn(
        "flex items-center gap-1.5 rounded-full px-2.5 py-0.5 font-medium tabular-nums",
        running
          ? left !== null && left <= 300
            ? "bg-fin-danger-bg text-fin-danger"
            : "bg-fin-pending-bg text-fin-pending"
          : "bg-hover text-text-muted",
      )}
    >
      <Clock className="size-3.5" />
      {running ? (left === null ? "—" : fmtCountdown(left)) : (STATE_LABEL[exam.state] ?? "Exam")}
    </Link>
  );
}
