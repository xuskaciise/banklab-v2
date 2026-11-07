"use client";

import Link from "next/link";
import {
  useClassSessions,
  useSessionTransition,
  useTemplates,
} from "@/lib/lab";
import type { SessionOut, TemplateOut } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import {
  ConfirmButton,
  Empty,
  ErrorMsg,
  formatTemplateLabel,
  QueryState,
  StatusBadge,
  Table,
  Td,
  Th,
} from "./common";
import { formatDateTime } from "@/lib/lab";

function SessionRow({ s }: { s: SessionOut }) {
  const t = useSessionTransition(s.id);
  return (
    <tr className="hover:bg-hover">
      <Td className="font-medium text-text-strong">{s.name}</Td>
      <Td className="capitalize">{s.kind}</Td>
      <Td>{s.structure === "per_group" ? "Per group" : "Single bank"}</Td>
      <Td>
        <StatusBadge status={s.status} />
      </Td>
      <Td className="text-text-muted">{formatDateTime(s.opened_at)}</Td>
      <Td>
        <div className="flex flex-wrap items-center gap-2">
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
              onConfirm={() => t.mutate({ action: "archive" })}
            />
          )}
          {s.status === "archived" && (
            <ConfirmButton
              label="Re-open"
              message="Re-open this archived session?"
              pending={t.isPending}
              onConfirm={() => t.mutate({ action: "reopen" })}
            />
          )}
        </div>
        <ErrorMsg error={t.error} />
      </Td>
    </tr>
  );
}

export function ClassSessionsTab({ classId }: { classId: string }) {
  const sessions = useClassSessions(classId);
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-text-strong">Sessions</h2>
        <Link href={`/instructor/sessions/new?classId=${classId}`}>
          <Button>Open new session</Button>
        </Link>
      </div>
      <QueryState query={sessions}>
        {sessions.data?.length ? (
          <Table>
            <thead>
              <tr>
                <Th>Name</Th>
                <Th>Kind</Th>
                <Th>Structure</Th>
                <Th>Status</Th>
                <Th>Opened</Th>
                <Th>Actions</Th>
              </tr>
            </thead>
            <tbody>
              {sessions.data.map((s) => (
                <SessionRow key={s.id} s={s} />
              ))}
            </tbody>
          </Table>
        ) : (
          <Empty>No sessions yet. Open a new session for this class.</Empty>
        )}
      </QueryState>
    </div>
  );
}

function TemplateRow({ t }: { t: TemplateOut }) {
  return (
    <tr className="hover:bg-hover">
      <Td className="font-medium text-text-strong">{t.name}</Td>
      <Td className="capitalize">{t.kind}</Td>
      <Td>{formatTemplateLabel(t.structure)}</Td>
      <Td>{t.allowed_roles.join(", ")}</Td>
      <Td>{t.default_visibility === "own" ? "Own work only" : "Whole bank"}</Td>
      <Td>{t.learning_panel ? "On" : "Off"}</Td>
      <Td className="text-text-muted">{t.class_id ? "This class" : "Institution"}</Td>
    </tr>
  );
}

export function TemplatesTab({ classId }: { classId: string }) {
  const templates = useTemplates(classId);
  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-text-strong">Templates</h2>
      <QueryState query={templates}>
        {templates.data?.length ? (
          <Table>
            <thead>
              <tr>
                <Th>Name</Th>
                <Th>Kind</Th>
                <Th>Structure</Th>
                <Th>Roles</Th>
                <Th>Visibility</Th>
                <Th>Dr/Cr panel</Th>
                <Th>Scope</Th>
              </tr>
            </thead>
            <tbody>
              {templates.data.map((t) => (
                <TemplateRow key={t.id} t={t} />
              ))}
            </tbody>
          </Table>
        ) : (
          <Empty>No templates available.</Empty>
        )}
      </QueryState>
    </div>
  );
}
