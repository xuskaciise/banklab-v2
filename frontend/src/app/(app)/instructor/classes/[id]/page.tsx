"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useClass } from "@/lib/lab";
import { PageHeader, QueryState, Tabs } from "@/components/lab/common";
import { StudentsTab } from "@/components/lab/students-tab";
import {
  ClassSessionsTab,
  TemplatesTab,
} from "@/components/lab/class-sessions-tab";

const TABS = [
  { id: "students", label: "Students" },
  { id: "sessions", label: "Sessions" },
  { id: "templates", label: "Templates" },
];

export default function ClassDetailPage() {
  const { id } = useParams<{ id: string }>();
  const cls = useClass(id);
  const [tab, setTab] = useState("students");
  return (
    <div>
      <p className="mb-2 text-sm">
        <Link href="/instructor/classes" className="text-bank-accent hover:underline">
          Classes
        </Link>
      </p>
      <QueryState query={cls}>
        {cls.data && (
          <>
            <PageHeader
              title={cls.data.name}
              subtitle={`${cls.data.code} · ${cls.data.instructor_name}`}
            />
            <Tabs tabs={TABS} value={tab} onChange={setTab} />
            {tab === "students" && <StudentsTab classId={id} />}
            {tab === "sessions" && <ClassSessionsTab classId={id} />}
            {tab === "templates" && <TemplatesTab classId={id} />}
          </>
        )}
      </QueryState>
    </div>
  );
}
