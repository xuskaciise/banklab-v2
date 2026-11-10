"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import {
  DateField,
  rangeError,
  ReportShell,
} from "@/components/reports/report-shell";
import { ReportView } from "@/components/reports/report-view";
import { ErrorMsg } from "@/components/lab/common";

export default function AccountStatementPage() {
  const { sessionId: sid, id } = useParams<{ sessionId: string; id: string }>();
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const err = rangeError(from, to);
  return (
    <ReportShell
      sid={sid}
      title="Account statement"
      subtitle="Opening balance, movements and closing balance."
      anyOf={["account.statement"]}
      back={{ href: `/s/${sid}/accounts/${id}`, label: "Account" }}
    >
      {err && <ErrorMsg error={new Error(err)} />}
      <ReportView
        sid={sid}
        slug="account-statement"
        ready={!err}
        params={{ account_id: id, date_from: from, date_to: to }}
        filters={
          <>
            <DateField label="From" value={from} onChange={setFrom} optional />
            <DateField label="To" value={to} onChange={setTo} optional />
          </>
        }
      />
    </ReportShell>
  );
}
