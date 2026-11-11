"use client";

import { useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { toast } from "sonner";
import { Check, Loader2, Play } from "lucide-react";
import type { BusinessDayOut, SessionOut } from "@/lib/api/types";
import {
  formatDateTime,
  roleLabel,
  useBusinessDays,
  useSessionTransition,
} from "@/lib/lab";
import { formatMoney } from "@/lib/banking";
import { useSosEnabled } from "@/lib/platform";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/shared/data-table";
import { FormGrid, FormSection } from "@/components/shared/form-layout";
import { StatusBadge } from "@/components/shared/status-badge";
import { ConfirmButton, ErrorMsg, formatTemplateLabel, Labeled, TextInput } from "./common";
import { VIS_OPTS } from "./session-options";

const STEPS = [
  { id: "draft", label: "Draft" },
  { id: "active", label: "Open" },
  { id: "archived", label: "Archived" },
];

function Stepper({ session }: { session: SessionOut }) {
  const cur = Math.max(0, STEPS.findIndex((s) => s.id === session.status));
  const when = [null, session.opened_at, session.archived_at];
  return (
    <ol className="flex items-start" aria-label="Session lifecycle">
      {STEPS.map((s, i) => {
        const done = i < cur;
        const here = i === cur;
        return (
          <li key={s.id} className="relative flex-1 text-center">
            {i > 0 && (
              <span
                aria-hidden
                className={cn(
                  "absolute top-4 right-1/2 h-0.5 w-full",
                  i <= cur ? "bg-bank-primary" : "bg-border",
                )}
              />
            )}
            <span
              aria-current={here ? "step" : undefined}
              className={cn(
                "relative mx-auto flex size-8 items-center justify-center rounded-full border-2 text-xs font-semibold",
                done && "border-bank-primary bg-bank-primary text-white",
                here && "border-bank-primary bg-bank-sky-light text-bank-primary",
                !done && !here && "border-border bg-card text-text-muted",
              )}
            >
              {done ? <Check className="size-4" aria-hidden /> : i + 1}
            </span>
            <p
              className={cn(
                "mt-1.5 text-sm",
                here ? "font-semibold text-text-strong" : "text-text-muted",
              )}
            >
              {s.label}
            </p>
            {when[i] && i <= cur && (
              <p className="text-xs text-text-muted">{formatDateTime(when[i])}</p>
            )}
          </li>
        );
      })}
    </ol>
  );
}

function Tile({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-3">
      <dt className="text-xs font-medium tracking-wide text-text-muted uppercase">
        {label}
      </dt>
      <dd className="mt-1 text-sm font-semibold text-text-strong">{children}</dd>
    </div>
  );
}

const dayColumns: ColumnDef<BusinessDayOut>[] = [
  {
    accessorKey: "bank_name",
    header: "Bank",
    cell: ({ getValue }) => (
      <span className="font-medium text-text-strong">{getValue<string>()}</span>
    ),
  },
  {
    accessorKey: "date",
    header: "Business date",
    cell: ({ getValue }) => <span className="tabular-nums">{getValue<string>()}</span>,
  },
  {
    accessorKey: "status",
    header: "Day status",
    cell: ({ getValue }) => <StatusBadge status={getValue<string>()} />,
  },
];

export function SettingsTab({ session }: { session: SessionOut }) {
  const sosOn = useSosEnabled();
  const showSos = sosOn || Number(session.opening_capital_sos) !== 0;
  const t = useSessionTransition(session.id);
  const days = useBusinessDays(session.id);
  const [groups, setGroups] = useState("2");
  const [groupErr, setGroupErr] = useState<string | null>(null);
  const perGroup = session.structure === "per_group";
  const ok = (m: string) => ({
    onSuccess: () => toast.success(m),
    onError: (e: Error) => toast.error(e.message),
  });

  function open() {
    if (perGroup) {
      const n = Number(groups);
      if (!Number.isInteger(n) || n < 1) {
        setGroupErr("Enter a whole number of groups (1 or more)");
        return;
      }
      setGroupErr(null);
      t.mutate({ action: "open", group_count: n }, ok("Session opened"));
    } else {
      t.mutate({ action: "open" }, ok("Session opened"));
    }
  }

  const vis = VIS_OPTS.find((o) => o.value === session.default_visibility);

  return (
    <div className="space-y-6">
      <FormSection
        title="Session status"
        description={
          session.status === "draft"
            ? "The session is a draft. Open it when members are ready."
            : session.status === "active"
              ? "The session is open for students."
              : "The session is archived and read-only."
        }
      >
        <div className="flex justify-end">
          <StatusBadge status={session.status} className="h-6 px-2.5 text-sm" />
        </div>
        <Stepper session={session} />
        <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Tile label="Kind">
            <span className="capitalize">{session.kind}</span>
          </Tile>
          <Tile label="Structure">
            {perGroup ? "One bank per group" : formatTemplateLabel(session.structure)}
          </Tile>
          <Tile label="Default visibility">
            {vis?.label ?? formatTemplateLabel(session.default_visibility)}
          </Tile>
          <Tile label="Learning panel">{session.learning_panel ? "On" : "Off"}</Tile>
          <Tile label="Opening capital (USD)">
            <span className="tabular-nums">
              {formatMoney(session.opening_capital_usd, "USD")}
            </span>
          </Tile>
          {showSos && (
            <Tile label="Opening capital (SOS)">
              <span className="tabular-nums">
                {formatMoney(session.opening_capital_sos, "SOS")}
              </span>
            </Tile>
          )}
          <div className="col-span-2">
            <Tile label="Allowed roles">
              <span className="font-normal text-text-body">
                {session.allowed_roles.map(roleLabel).join(", ") || "None"}
              </span>
            </Tile>
          </div>
        </dl>
      </FormSection>

      {session.status === "draft" && (
        <FormSection
          title="Open the session"
          description="Opening creates each bank's first business day and locks the session structure. Students can then sign in and work."
        >
          {perGroup && (
            <FormGrid>
              <Labeled
                label="Number of groups"
                required
                error={groupErr ?? undefined}
                hint="One bank is created per group."
              >
                <TextInput
                  type="number"
                  min={1}
                  value={groups}
                  onChange={(e) => setGroups(e.target.value)}
                />
              </Labeled>
            </FormGrid>
          )}
          <ErrorMsg error={t.error} />
          <div className="flex justify-end">
            <Button disabled={t.isPending} onClick={open}>
              {t.isPending ? (
                <Loader2 className="animate-spin" aria-hidden />
              ) : (
                <Play aria-hidden />
              )}
              {t.isPending ? "Opening…" : "Open session"}
            </Button>
          </div>
        </FormSection>
      )}

      {session.status !== "draft" && (
        <section className="rounded-xl border border-fin-danger/30 bg-fin-danger-bg/40 p-5">
          <h2 className="text-sm font-semibold text-text-strong">Danger zone</h2>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
            <p className="max-w-xl text-sm text-text-body">
              {session.status === "active"
                ? "Archiving makes the session read-only for everyone. You can re-open it later."
                : "Re-opening lets members post again in this session."}
            </p>
            {session.status === "active" ? (
              <ConfirmButton
                label="Archive session"
                message="Archive this session? It becomes read-only for everyone."
                variant="destructive"
                size="default"
                pending={t.isPending}
                onConfirm={() => t.mutate({ action: "archive" }, ok("Session archived"))}
              />
            ) : (
              <ConfirmButton
                label="Re-open session"
                message="Re-open this archived session?"
                size="default"
                pending={t.isPending}
                onConfirm={() => t.mutate({ action: "reopen" }, ok("Session re-opened"))}
              />
            )}
          </div>
          <ErrorMsg error={t.error} />
        </section>
      )}

      <FormSection
        title="Business date per bank"
        description="Each bank keeps its own business date once the session is open."
      >
        {!days.isPending && !days.error && days.data?.length === 0 ? (
          <p className="rounded-lg bg-surface px-4 py-3 text-sm text-text-muted">
            No business days yet. They appear once the session is open.
          </p>
        ) : (
        <DataTable
          columns={dayColumns}
          data={days.data}
          isLoading={days.isPending}
          error={days.error}
          getRowId={(d) => d.bank_id}
          columnToggle={false}
          searchPlaceholder="Search banks…"
          emptyTitle="No business days yet"
          emptyDescription="Business days appear once the session is open."
        />
        )}
      </FormSection>
    </div>
  );
}
