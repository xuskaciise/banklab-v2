"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { Select } from "@/components/ui/input";
import { Labeled } from "@/components/lab/common";
import { ReportShell } from "@/components/reports/report-shell";
import { ReportView } from "@/components/reports/report-view";
import { useTellerSessions } from "@/lib/tellers";

export default function TellerCashPage() {
  const { sessionId: sid } = useParams<{ sessionId: string }>();
  const [tsId, setTsId] = useState("");
  const list = useTellerSessions(sid);
  const options = (list.data ?? []).filter(
    (t) => t.status !== "pending_open" && t.status !== "cancelled",
  );
  return (
    <ReportShell
      sid={sid}
      title="Teller Cash Report"
      subtitle="Cash position of one teller session."
      anyOf={["report.operational"]}
    >
      <ReportView
        sid={sid}
        slug="teller-cash"
        ready={!!tsId}
        params={{ teller_session_id: tsId }}
        filters={
          <Labeled
            label="Teller session"
            required
            error={list.isError ? "Could not load teller sessions." : undefined}
            hint={
              list.isSuccess && options.length === 0
                ? "No teller sessions yet."
                : undefined
            }
          >
            <Select
              value={tsId}
              onChange={(e) => setTsId(e.target.value)}
              className="w-80"
            >
              <option value="">Select a session</option>
              {options.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.till_code} - {t.teller_name ?? "Teller"} - {t.business_date} ({t.status})
                </option>
              ))}
            </Select>
          </Labeled>
        }
      />
    </ReportShell>
  );
}
