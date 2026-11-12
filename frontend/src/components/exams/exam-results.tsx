"use client";

import { Fragment, useState } from "react";
import { ChevronDown, ChevronRight, Download } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { EmptyState } from "@/components/shared/empty-state";
import {
  errorText,
  ErrorMsg,
  QueryState,
  StatusBadge,
  Table,
  Td,
  TextInput,
  Th,
} from "@/components/lab/common";
import type { ExamStudentRow, ExamTaskResult } from "@/lib/api/types";
import {
  downloadExamResults,
  fmtPoints,
  useAdjustResult,
  useExamResults,
  usePublishResults,
} from "@/lib/exams";
import { formatDateTime } from "@/lib/lab";

const STATUS_TONE = {
  not_started: "muted",
  in_progress: "pending",
  submitted: "success",
} as const;

function detailsText(d: Record<string, unknown>) {
  return Object.entries(d)
    .map(([k, v]) => `${k.replace(/_/g, " ")}: ${String(v)}`)
    .join(" · ");
}

function TaskRow({
  sid,
  t,
  editable,
}: {
  sid: string;
  t: ExamTaskResult;
  editable: boolean;
}) {
  const adjust = useAdjustResult(sid);
  const [val, setVal] = useState(t.adjusted_points == null ? "" : fmtPoints(t.adjusted_points));
  const [err, setErr] = useState("");
  const max = Number(t.max_points);

  function apply(points: number | null) {
    setErr("");
    adjust.mutate(
      { resultId: t.result_id, points },
      {
        onSuccess: () => {
          toast.success(points === null ? "Adjustment cleared" : "Points adjusted");
          if (points === null) setVal("");
        },
        onError: (e) => setErr(errorText(e)),
      },
    );
  }
  function save() {
    const n = Number(val);
    if (val.trim() === "" || !Number.isFinite(n) || n < 0 || n > max) {
      setErr(`Enter points from 0 to ${fmtPoints(max)}.`);
      return;
    }
    apply(n);
  }

  return (
    <tr className="bg-surface text-sm">
      <td className="py-2 pr-3 pl-12">
        <p className="font-medium text-text-strong">{t.title}</p>
        <p className="text-xs break-words text-text-muted">{detailsText(t.details)}</p>
      </td>
      <td className="px-3 py-2">
        <StatusBadge status={t.passed ? "passed" : "not passed"} tone={t.passed ? "success" : "danger"} />
      </td>
      <td className="px-3 py-2 whitespace-nowrap text-text-muted tabular-nums">
        auto {fmtPoints(t.auto_points)} / {fmtPoints(t.max_points)}
      </td>
      <td className="px-3 py-2" colSpan={2}>
        <div className="flex flex-wrap items-center gap-2">
          {editable ? (
            <>
              <TextInput
                aria-label={`Adjusted points for ${t.title}`}
                inputMode="decimal"
                placeholder="Adjust"
                className="h-8 w-24"
                value={val}
                onChange={(e) => setVal(e.target.value)}
              />
              <Button size="sm" variant="outline" disabled={adjust.isPending} onClick={save}>
                Set
              </Button>
              {t.adjusted_points != null && (
                <Button size="sm" variant="ghost" disabled={adjust.isPending} onClick={() => apply(null)}>
                  Clear
                </Button>
              )}
            </>
          ) : (
            t.adjusted_points != null && (
              <span className="text-text-muted">adjusted {fmtPoints(t.adjusted_points)}</span>
            )
          )}
          <span className="font-semibold text-text-strong tabular-nums">= {fmtPoints(t.points)}</span>
        </div>
        {err && <p className="mt-1 text-xs text-fin-danger">{err}</p>}
      </td>
    </tr>
  );
}

function StudentRows({
  sid,
  s,
  max,
}: {
  sid: string;
  s: ExamStudentRow;
  max: number | string;
}) {
  const [open, setOpen] = useState(false);
  const can = s.tasks.length > 0;
  return (
    <Fragment>
      <tr>
        <Td>
          <button
            type="button"
            disabled={!can}
            aria-expanded={open}
            onClick={() => setOpen((o) => !o)}
            className="flex items-center gap-2 font-medium text-text-strong disabled:cursor-default"
          >
            {can ? (
              open ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />
            ) : (
              <span className="size-4" />
            )}
            {s.full_name}
          </button>
        </Td>
        <Td className="text-text-muted">{s.username}</Td>
        <Td>
          <StatusBadge
            status={s.status}
            tone={STATUS_TONE[s.status as keyof typeof STATUS_TONE] ?? "muted"}
          />
          {s.auto_submitted && <span className="ml-2 text-xs text-text-muted">auto-submitted</span>}
        </Td>
        <Td className="text-text-muted">{s.submitted_at ? formatDateTime(s.submitted_at) : "—"}</Td>
        <Td className="text-right font-semibold text-text-strong tabular-nums">
          {s.score == null ? "—" : `${fmtPoints(s.score)} / ${fmtPoints(max)}`}
        </Td>
      </tr>
      {open &&
        s.tasks.map((t) => (
          <TaskRow key={t.result_id} sid={sid} t={t} editable={s.status === "submitted"} />
        ))}
    </Fragment>
  );
}

export function ExamResultsView({ sid }: { sid: string }) {
  const q = useExamResults(sid);
  const publish = usePublishResults(sid);
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState<"pdf" | "xlsx" | null>(null);

  async function download(ext: "pdf" | "xlsx") {
    setBusy(ext);
    try {
      await downloadExamResults(sid, ext);
    } catch (e) {
      toast.error(errorText(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <QueryState query={q}>
      {q.data && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card p-4 shadow-xs">
            <div className="flex flex-wrap items-center gap-3 text-sm text-text-muted">
              <StatusBadge
                status={q.data.results_published ? "published" : "draft"}
                label={q.data.results_published ? "Results published" : "Results not published"}
                tone={q.data.results_published ? "success" : "pending"}
              />
              <span>
                Max score{" "}
                <span className="font-semibold text-text-strong tabular-nums">{fmtPoints(q.data.max_score)}</span>
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" disabled={busy !== null} onClick={() => download("xlsx")}>
                <Download /> Excel
              </Button>
              <Button variant="outline" disabled={busy !== null} onClick={() => download("pdf")}>
                <Download /> PDF
              </Button>
              {!q.data.results_published && (
                <Button onClick={() => setConfirm(true)}>Publish results</Button>
              )}
            </div>
          </div>
          <ErrorMsg error={publish.error} />
          {q.data.students.length === 0 ? (
            <EmptyState title="No students" description="No students are in this exam session yet." />
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th>Student</Th>
                  <Th>Username</Th>
                  <Th>Status</Th>
                  <Th>Submitted</Th>
                  <Th className="text-right">Score</Th>
                </tr>
              </thead>
              <tbody>
                {q.data.students.map((s) => (
                  <StudentRows key={s.member_id} sid={sid} s={s} max={q.data.max_score} />
                ))}
              </tbody>
            </Table>
          )}
          <ConfirmDialog
            open={confirm}
            onOpenChange={setConfirm}
            title="Publish results?"
            description="Students will be able to see their score and per-task points. This cannot be undone."
            confirmLabel="Publish results"
            pending={publish.isPending}
            onConfirm={() =>
              publish.mutate(undefined, {
                onSuccess: () => {
                  setConfirm(false);
                  toast.success("Results published");
                },
                onError: () => setConfirm(false),
              })
            }
          />
        </div>
      )}
    </QueryState>
  );
}
