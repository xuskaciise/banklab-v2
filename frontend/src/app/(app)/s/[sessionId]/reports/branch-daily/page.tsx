"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { DateField, ReportShell } from "@/components/reports/report-shell";
import { ReportView } from "@/components/reports/report-view";

export default function BranchDailyPage() {
  const { sessionId: sid } = useParams<{ sessionId: string }>();
  const [date, setDate] = useState("");
  return (
    <ReportShell
      sid={sid}
      title="Branch Daily Report"
      subtitle="Leave the date empty for the current business date."
      anyOf={["report.operational"]}
    >
      <ReportView
        sid={sid}
        slug="branch-daily"
        params={{ business_date: date }}
        filters={
          <DateField label="Business date" value={date} onChange={setDate} optional />
        }
      />
    </ReportShell>
  );
}
