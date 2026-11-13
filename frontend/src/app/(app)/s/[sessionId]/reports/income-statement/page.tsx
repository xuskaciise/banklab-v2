"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import {
  CurrencyField,
  DateField,
  rangeError,
  ReportShell,
} from "@/components/reports/report-shell";
import { ReportView } from "@/components/reports/report-view";
import { ErrorMsg } from "@/components/lab/common";

export default function IncomeStatementPage() {
  const { sessionId: sid } = useParams<{ sessionId: string }>();
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [currency, setCurrency] = useState("");
  const err = rangeError(from, to);
  return (
    <ReportShell
      sid={sid}
      title="Income Statement"
      subtitle="Income and expenses for the selected dates."
      anyOf={["report.financial"]}
    >
      {err && <ErrorMsg error={new Error(err)} />}
      <ReportView
        sid={sid}
        slug="income-statement"
        ready={!err}
        params={{ date_from: from, date_to: to, currency }}
        filters={
          <>
            <DateField label="From" value={from} onChange={setFrom} optional />
            <DateField label="To" value={to} onChange={setTo} optional />
            <CurrencyField value={currency} onChange={setCurrency} allowAll />
          </>
        }
      />
    </ReportShell>
  );
}
