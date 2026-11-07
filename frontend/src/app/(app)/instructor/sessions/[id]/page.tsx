"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useSession } from "@/lib/lab";
import {
  PageHeader,
  QueryState,
  ReadOnlyBanner,
  StatusBadge,
  Tabs,
} from "@/components/lab/common";
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
  { id: "members", label: "Members" },
  { id: "banks", label: "Banks" },
  { id: "permissions", label: "Permissions" },
  { id: "activity", label: "Activity" },
  { id: "settings", label: "Settings" },
];

export default function SessionControlPage() {
  const { id } = useParams<{ id: string }>();
  const session = useSession(id);
  const [tab, setTab] = useState("members");
  const s = session.data;
  const readOnly = s?.status === "archived";
  return (
    <div>
      <QueryState query={session}>
        {s && (
          <>
            <p className="mb-2 text-sm">
              <Link
                href={`/instructor/classes/${s.class_id}`}
                className="text-bank-accent hover:underline"
              >
                {s.class_name}
              </Link>
            </p>
            <PageHeader
              title={
                <span className="flex items-center gap-3">
                  {s.name} <StatusBadge status={s.status} />
                </span>
              }
              subtitle={`${s.kind === "exam" ? "Exam" : "Practice"} session`}
            />
            {readOnly && <ReadOnlyBanner />}
            <Tabs tabs={TABS} value={tab} onChange={setTab} />
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
