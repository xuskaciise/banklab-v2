"use client";

import Link from "next/link";
import type { ColumnDef } from "@tanstack/react-table";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import {
  formatDateTime,
  useClassSessions,
  useSessionTransition,
  useTemplates,
} from "@/lib/lab";
import type { SessionOut, TemplateOut } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/shared/data-table";
import { StatusBadge } from "@/components/shared/status-badge";
import { ConfirmButton, formatTemplateLabel } from "./common";

function SessionActions({ s }: { s: SessionOut }) {
  const t = useSessionTransition(s.id);
  const run = (action: "archive" | "reopen", done: string) =>
    t.mutate(
      { action },
      {
        onSuccess: () => toast.success(done),
        onError: (e) => toast.error(e.message),
      },
    );
  return (
    <div className="flex items-center justify-end gap-2">
      <Link href={`/instructor/sessions/${s.id}`}>
        <Button size="sm" variant="outline">
          {s.status === "draft" ? "Set up / open" : "Control"}
        </Button>
      </Link>
      {s.status === "active" && (
        <ConfirmButton
          label="Archive"
          message="Archive this session? It becomes read-only."
          pending={t.isPending}
          onConfirm={() => run("archive", `${s.name} archived`)}
        />
      )}
      {s.status === "archived" && (
        <ConfirmButton
          label="Re-open"
          message="Re-open this archived session?"
          pending={t.isPending}
          onConfirm={() => run("reopen", `${s.name} re-opened`)}
        />
      )}
    </div>
  );
}

const sessionColumns: ColumnDef<SessionOut>[] = [
  {
    accessorKey: "name",
    header: "Session",
    cell: ({ row }) => (
      <Link
        href={`/instructor/sessions/${row.original.id}`}
        className="font-medium text-text-strong hover:text-bank-accent hover:underline"
      >
        {row.original.name}
      </Link>
    ),
  },
  {
    accessorKey: "kind",
    header: "Kind",
    cell: ({ getValue }) => <span className="capitalize">{getValue<string>()}</span>,
  },
  {
    accessorKey: "structure",
    header: "Structure",
    cell: ({ getValue }) => formatTemplateLabel(getValue<string>()),
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ getValue }) => <StatusBadge status={getValue<string>()} />,
  },
  {
    accessorKey: "opened_at",
    header: "Opened",
    cell: ({ getValue }) => (
      <span className="text-text-muted">{formatDateTime(getValue<string | null>())}</span>
    ),
  },
  {
    id: "actions",
    header: () => <span className="sr-only">Actions</span>,
    enableSorting: false,
    enableHiding: false,
    meta: { className: "text-right" },
    cell: ({ row }) => <SessionActions s={row.original} />,
  },
];

export function ClassSessionsTab({ classId }: { classId: string }) {
  const sessions = useClassSessions(classId);
  const newBtn = (
    <Link href={`/instructor/sessions/new?classId=${classId}`}>
      <Button size="sm">
        <Plus /> New session
      </Button>
    </Link>
  );
  return (
    <DataTable
      columns={sessionColumns}
      data={sessions.data}
      isLoading={sessions.isPending}
      error={sessions.error}
      getRowId={(s) => s.id}
      searchPlaceholder="Search sessions…"
      toolbar={newBtn}
      emptyTitle="No sessions yet"
      emptyDescription="Open a new session for this class."
      emptyAction={newBtn}
    />
  );
}

const templateColumns: ColumnDef<TemplateOut>[] = [
  {
    accessorKey: "name",
    header: "Template",
    cell: ({ getValue }) => (
      <span className="font-medium text-text-strong">{getValue<string>()}</span>
    ),
  },
  {
    accessorKey: "kind",
    header: "Kind",
    cell: ({ getValue }) => <span className="capitalize">{getValue<string>()}</span>,
  },
  {
    accessorKey: "structure",
    header: "Structure",
    cell: ({ getValue }) => formatTemplateLabel(getValue<string>()),
  },
  {
    id: "roles",
    header: "Roles",
    enableSorting: false,
    accessorFn: (t) => t.allowed_roles.join(", "),
  },
  {
    accessorKey: "default_visibility",
    header: "Visibility",
    cell: ({ getValue }) =>
      getValue<string>() === "own" ? "Own work only" : "Whole bank",
  },
  {
    accessorKey: "learning_panel",
    header: "Dr/Cr panel",
    cell: ({ getValue }) => (getValue<boolean>() ? "On" : "Off"),
  },
  {
    id: "scope",
    header: "Scope",
    accessorFn: (t) => (t.class_id ? "This class" : "Institution"),
    cell: ({ getValue }) => (
      <span className="text-text-muted">{getValue<string>()}</span>
    ),
  },
];

export function TemplatesTab({ classId }: { classId: string }) {
  const templates = useTemplates(classId);
  return (
    <DataTable
      columns={templateColumns}
      data={templates.data}
      isLoading={templates.isPending}
      error={templates.error}
      getRowId={(t) => t.id}
      searchPlaceholder="Search templates…"
      emptyTitle="No templates available"
    />
  );
}
