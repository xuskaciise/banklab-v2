"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useBanks, useMembers, useSession } from "@/lib/lab";
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

const TABS = (counts: { members?: number; banks?: number }) => [
  { id: "overview", label: "Overview" },
  { id: "members", label: "Members", count: counts.members },
  { id: "banks", label: "Banks", count: counts.banks },
  { id: "permissions", label: "Permissions" },
  { id: "activity", label: "Activity" },
  { id: "settings", label: "Settings" },
];

export default function SessionControlPage() {
  const { id } = useParams<{ id: string }>();
  const session = useSession(id);
  const members = useMembers(id);
  const banks = useBanks(id);
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
            <Tabs tabs={TABS({ members: members.data?.length, banks: banks.data?.length })} value={tab} onChange={setTab} />
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
