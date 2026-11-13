"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowDown, ArrowUp, Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorMsg, Labeled, Select, StatusBadge, TextInput } from "@/components/lab/common";
import { TaskDialog } from "@/components/exams/task-dialog";
import type { ExamOut, ExamTask } from "@/lib/api/types";
import { errorText } from "@/components/lab/common";
import {
  fmtPoints,
  isoToLocal,
  localToIso,
  PRODUCT_CODES,
  useCheckTypes,
  useCreateTask,
  useDeleteTask,
  usePublishExam,
  useReorderTasks,
  useSaveExam,
  useUpdateTask,
} from "@/lib/exams";
import { formatDateTime } from "@/lib/lab";

type SeedRow = { product_code: string; amount: string; vary: boolean };

function Card({ title, children, actions }: { title: string; children: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-border bg-card p-5 shadow-xs">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold text-text-strong">{title}</h2>
        {actions}
      </div>
      {children}
    </section>
  );
}

function ExamForm({
  sid,
  exam,
  locked,
}: {
  sid: string;
  exam: ExamOut | null;
  locked: boolean;
}) {
  const save = useSaveExam(sid);
  const [startsAt, setStartsAt] = useState(exam ? isoToLocal(exam.starts_at) : "");
  const [endsAt, setEndsAt] = useState(exam ? isoToLocal(exam.ends_at) : "");
  const [duration, setDuration] = useState(String(exam?.duration_minutes ?? 60));
  const [instructions, setInstructions] = useState(exam?.instructions ?? "");
  const [seed, setSeed] = useState<SeedRow[]>(
    (exam?.seed ?? []).map((s) => ({
      product_code: String(s.product_code ?? PRODUCT_CODES[0]),
      amount: String(s.amount ?? ""),
      vary: !!s.vary,
    })),
  );
  const [errs, setErrs] = useState<Record<string, string>>({});

  const setRow = (i: number, patch: Partial<SeedRow>) =>
    setSeed((rows) => rows.map((r, k) => (k === i ? { ...r, ...patch } : r)));

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const next: Record<string, string> = {};
    if (!startsAt) next.starts_at = "Choose when the exam opens.";
    if (!endsAt) next.ends_at = "Choose when the exam closes.";
    if (startsAt && endsAt && new Date(endsAt) <= new Date(startsAt))
      next.ends_at = "The end must be after the start.";
    const dur = Number(duration);
    if (!Number.isInteger(dur) || dur < 1) next.duration = "Duration must be a whole number of minutes.";
    seed.forEach((r, i) => {
      const a = Number(r.amount);
      if (r.amount.trim() === "" || !Number.isFinite(a) || a < 0)
        next[`seed${i}`] = "Enter a valid amount.";
    });
    setErrs(next);
    if (Object.keys(next).length) return;
    save.mutate(
      {
        starts_at: localToIso(startsAt),
        ends_at: localToIso(endsAt),
        duration_minutes: dur,
        instructions: instructions.trim(),
        seed: seed.map((r) => ({
          product_code: r.product_code,
          amount: r.amount.trim(),
          vary: r.vary,
        })),
      },
      { onSuccess: () => toast.success("Exam settings saved") },
    );
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-6">
      <Card title="Timing and instructions">
        <fieldset disabled={locked} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <Labeled label="Opens at" required error={errs.starts_at} hint="Your local time">
              <TextInput type="datetime-local" value={startsAt} onChange={(e) => setStartsAt(e.target.value)} />
            </Labeled>
            <Labeled label="Closes at" required error={errs.ends_at}>
              <TextInput type="datetime-local" value={endsAt} onChange={(e) => setEndsAt(e.target.value)} />
            </Labeled>
            <Labeled label="Duration (minutes)" required error={errs.duration} hint="Per student, from Start">
              <TextInput inputMode="numeric" value={duration} onChange={(e) => setDuration(e.target.value)} />
            </Labeled>
          </div>
          <Labeled label="Instructions" optional>
            <Textarea
              rows={5}
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              placeholder="General instructions shown to students before they start."
            />
          </Labeled>
        </fieldset>
      </Card>

      <Card
        title="Seed accounts"
        actions={
          !locked && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setSeed((r) => [...r, { product_code: PRODUCT_CODES[0], amount: "", vary: false }])}
            >
              <Plus /> Add account
            </Button>
          )
        }
      >
        <p className="mb-3 text-sm text-text-muted">
          Accounts each student starts with. Tasks can refer to them by position (first = 0).
        </p>
        {seed.length === 0 ? (
          <p className="text-sm text-text-muted">No seed accounts.</p>
        ) : (
          <ul className="space-y-3">
            {seed.map((r, i) => (
              <li key={i} className="grid items-start gap-3 sm:grid-cols-[2rem_1fr_1fr_auto_auto]">
                <span className="pt-2.5 text-sm tabular-nums text-text-muted">#{i}</span>
                <Select className="w-full" disabled={locked} aria-label="Product" value={r.product_code} onChange={(e) => setRow(i, { product_code: e.target.value })}>
                  {PRODUCT_CODES.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </Select>
                <div>
                  <TextInput
                    aria-label="Opening balance"
                    placeholder="Opening balance"
                    inputMode="decimal"
                    disabled={locked}
                    value={r.amount}
                    onChange={(e) => setRow(i, { amount: e.target.value })}
                  />
                  {errs[`seed${i}`] && <p className="mt-1 text-sm text-fin-danger">{errs[`seed${i}`]}</p>}
                </div>
                <label className="flex h-11 items-center gap-2 text-sm text-text-body sm:h-11">
                  <input
                    type="checkbox"
                    className="size-4 accent-[var(--color-bank-primary)]"
                    disabled={locked}
                    checked={r.vary}
                    onChange={(e) => setRow(i, { vary: e.target.checked })}
                  />
                  Vary per student
                </label>
                {!locked && (
                  <Button type="button" variant="ghost" size="icon" aria-label="Remove seed account" onClick={() => setSeed((rows) => rows.filter((_, k) => k !== i))}>
                    <Trash2 />
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>

      {!locked && (
        <div className="space-y-3">
          <ErrorMsg error={save.error} />
          <Button type="submit" disabled={save.isPending}>
            {save.isPending ? "Saving…" : exam ? "Save settings" : "Create exam"}
          </Button>
        </div>
      )}
    </form>
  );
}

function describeParams(t: ExamTask) {
  const p = t.check_params;
  return Object.entries(p)
    .map(([k, v]) => `${k.replace(/_/g, " ")}: ${String(v)}`)
    .join(" · ");
}

function TasksCard({ sid, exam, locked }: { sid: string; exam: ExamOut; locked: boolean }) {
  const types = useCheckTypes();
  const create = useCreateTask(sid);
  const update = useUpdateTask(sid);
  const del = useDeleteTask(sid);
  const reorder = useReorderTasks(sid);
  const [dialog, setDialog] = useState<{ task: ExamTask | null } | null>(null);
  const [toDelete, setToDelete] = useState<ExamTask | null>(null);
  const tasks = [...exam.tasks].sort((a, b) => a.position - b.position);
  const label = (n: string) => types.data?.find((t) => t.name === n)?.label ?? n;

  function move(i: number, dir: -1 | 1) {
    const ids = tasks.map((t) => t.id);
    [ids[i], ids[i + dir]] = [ids[i + dir], ids[i]];
    reorder.mutate(ids, { onError: (e) => toast.error(errorText(e)) });
  }

  const dialogMut = dialog?.task ? update : create;
  return (
    <Card
      title={`Tasks (${tasks.length})`}
      actions={
        !locked && (
          <Button type="button" size="sm" disabled={!types.data} onClick={() => setDialog({ task: null })}>
            <Plus /> Add task
          </Button>
        )
      }
    >
      {tasks.length === 0 ? (
        <EmptyState title="No tasks yet" description="Add the tasks students must complete. Each is checked automatically." />
      ) : (
        <ol className="divide-y divide-border">
          {tasks.map((t, i) => (
            <li key={t.id} className="flex flex-wrap items-start gap-3 py-3">
              <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-bank-sky-light text-xs font-semibold text-bank-primary">
                {i + 1}
              </span>
              <div className="min-w-0 flex-1">
                <p className="font-medium text-text-strong">{t.title}</p>
                <p className="text-xs text-text-muted">
                  {label(t.check_type)} · {fmtPoints(t.points)} pts
                </p>
                <p className="mt-0.5 text-xs break-words text-text-muted">{describeParams(t)}</p>
              </div>
              {!locked && (
                <div className="flex items-center gap-1">
                  <Button type="button" variant="ghost" size="icon" aria-label="Move up" disabled={i === 0 || reorder.isPending} onClick={() => move(i, -1)}>
                    <ArrowUp />
                  </Button>
                  <Button type="button" variant="ghost" size="icon" aria-label="Move down" disabled={i === tasks.length - 1 || reorder.isPending} onClick={() => move(i, 1)}>
                    <ArrowDown />
                  </Button>
                  <Button type="button" variant="ghost" size="icon" aria-label="Edit task" onClick={() => setDialog({ task: t })}>
                    <Pencil />
                  </Button>
                  <Button type="button" variant="ghost" size="icon" aria-label="Delete task" onClick={() => setToDelete(t)}>
                    <Trash2 className="text-fin-danger" />
                  </Button>
                </div>
              )}
            </li>
          ))}
        </ol>
      )}
      {dialog && types.data && (
        <TaskDialog
          key={dialog.task?.id ?? "new"}
          open
          onOpenChange={(o) => !o && setDialog(null)}
          task={dialog.task}
          checkTypes={types.data}
          pending={dialogMut.isPending}
          error={dialogMut.error}
          onSubmit={(body) => {
            const done = {
              onSuccess: () => {
                toast.success(dialog.task ? "Task updated" : "Task added");
                setDialog(null);
              },
            };
            if (dialog.task) update.mutate({ id: dialog.task.id, patch: body }, done);
            else create.mutate(body, done);
          }}
        />
      )}
      <ConfirmDialog
        open={!!toDelete}
        onOpenChange={(o) => !o && setToDelete(null)}
        title="Delete task?"
        description={toDelete ? `"${toDelete.title}" will be removed from the exam.` : undefined}
        confirmLabel="Delete"
        destructive
        pending={del.isPending}
        onConfirm={() =>
          toDelete &&
          del.mutate(toDelete.id, {
            onSuccess: () => setToDelete(null),
            onError: (e) => {
              toast.error(errorText(e));
              setToDelete(null);
            },
          })
        }
      />
    </Card>
  );
}

export function ExamSetup({ sid, exam }: { sid: string; exam: ExamOut | null }) {
  const publish = usePublishExam(sid);
  const [confirm, setConfirm] = useState(false);
  const locked = exam?.status === "published";
  return (
    <div className="space-y-6">
      {exam && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card p-4 shadow-xs">
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <StatusBadge status={exam.status} tone={locked ? "success" : "pending"} />
            <span className="text-text-muted">
              Total points{" "}
              <span className="font-semibold text-text-strong tabular-nums">{fmtPoints(exam.total_points)}</span>
            </span>
            {locked && exam.published_at && (
              <span className="text-text-muted">Published {formatDateTime(exam.published_at)}</span>
            )}
          </div>
          <div className="flex gap-2">
            {locked ? (
              <Button variant="outline" nativeButton={false} render={<Link href={`/instructor/exams/${sid}/results`} />}>
                View results
              </Button>
            ) : (
              <Button disabled={exam.tasks.length === 0} onClick={() => setConfirm(true)}>
                Publish exam
              </Button>
            )}
          </div>
        </div>
      )}
      {locked && (
        <div role="status" className="rounded-lg border border-fin-pending/30 bg-fin-pending-bg px-4 py-2.5 text-sm font-medium text-fin-pending">
          This exam is published and can no longer be edited.
        </div>
      )}
      <ErrorMsg error={publish.error} />
      <ExamForm key={exam?.id ?? "new"} sid={sid} exam={exam} locked={locked} />
      {exam ? (
        <TasksCard sid={sid} exam={exam} locked={locked} />
      ) : (
        <p className="text-sm text-text-muted">Create the exam first, then add tasks.</p>
      )}
      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title="Publish exam?"
        description="Students will see the exam at the opening time. After publishing, the timing, seed accounts and tasks cannot be changed."
        confirmLabel="Publish"
        pending={publish.isPending}
        onConfirm={() =>
          publish.mutate(undefined, {
            onSuccess: () => {
              setConfirm(false);
              toast.success("Exam published");
            },
            onError: () => setConfirm(false),
          })
        }
      />
    </div>
  );
}
