"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useSession } from "@/lib/lab";
import { PageHeader } from "@/components/shared/page-header";
import { StatusBadge } from "@/components/shared/status-badge";
import { QueryState, ReadOnlyBanner, Tabs } from "@/components/lab/common";
import { OverviewTab } from "@/components/lab/session-overview-tab";
import {
  BanksTab,
  MembersTab,
} from "@/components/lab/session-members-banks";
import {
  ActivityTab,
  PermissionsTab,
  SettingsTab,
} from "@/components/lab/session-admin-tabs";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "members", label: "Members" },
  { id: "banks", label: "Banks" },
  { id: "permissions", label: "Permissions" },
  { id: "activity", label: "Activity" },
  { id: "settings", label: "Settings" },
];

export default function SessionControlPage() {
  const { id } = useParams<{ id: string }>();
  const session = useSession(id);
  const [tab, setTab] = useState("overview");
  const s = session.data;
  const readOnly = s?.status === "archived";
  return (
    <div>
      <QueryState query={session}>
        {s && (
          <>
            <PageHeader
              title={
                <span className="flex flex-wrap items-center gap-3">
                  {s.name} <StatusBadge status={s.status} />
                </span>
              }
              subtitle={`${s.class_name} · ${s.kind === "exam" ? "Exam" : "Practice"} session`}
            />
            {readOnly && <ReadOnlyBanner />}
            <Tabs tabs={TABS} value={tab} onChange={setTab} />
            {tab === "overview" && <OverviewTab session={s} />}
            {tab === "members" && <MembersTab session={s} readOnly={readOnly} />}
            {tab === "banks" && <BanksTab session={s} readOnly={readOnly} />}
            {tab === "permissions" && (
              <PermissionsTab session={s} readOnly={readOnly} />
            )}
            {tab === "activity" && <ActivityTab sessionId={s.id} />}
            {tab === "settings" && <SettingsTab session={s} />}
          </>
        )}
      </QueryState>
    </div>
  );
}
