"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Plus, Upload } from "lucide-react";
import { useClass, useClassSessions, useStudents } from "@/lib/lab";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/shared/page-header";
import { QueryState, Tabs } from "@/components/lab/common";
import { StudentsTab } from "@/components/lab/students-tab";
import {
  ClassSessionsTab,
  TemplatesTab,
} from "@/components/lab/class-sessions-tab";

export default function ClassDetailPage() {
  const { id } = useParams<{ id: string }>();
  const cls = useClass(id);
  const students = useStudents(id);
  const sessions = useClassSessions(id);
  const [tab, setTab] = useState("students");
  const tabs = [
    {
      id: "students",
      label: `Students${students.data ? ` (${students.data.length})` : ""}`,
    },
    {
      id: "sessions",
      label: `Sessions${sessions.data ? ` (${sessions.data.length})` : ""}`,
    },
    { id: "templates", label: "Templates" },
  ];
  return (
    <div>
      <QueryState query={cls}>
        {cls.data && (
          <>
            <PageHeader
              title={cls.data.name}
              subtitle={
                <>
                  <span className="font-mono text-xs">{cls.data.code}</span>
                  {" · "}
                  {cls.data.instructor_name}
                </>
              }
              actions={
                <>
                  <Link href={`/instructor/classes/${id}/import`}>
                    <Button variant="outline">
                      <Upload /> Import CSV
                    </Button>
                  </Link>
                  <Link href={`/instructor/sessions/new?classId=${id}`}>
                    <Button>
                      <Plus /> New session
                    </Button>
                  </Link>
                </>
              }
            />
            <Tabs tabs={tabs} value={tab} onChange={setTab} />
            {tab === "students" && <StudentsTab classId={id} />}
            {tab === "sessions" && <ClassSessionsTab classId={id} />}
            {tab === "templates" && <TemplatesTab classId={id} />}
          </>
        )}
      </QueryState>
    </div>
  );
}
