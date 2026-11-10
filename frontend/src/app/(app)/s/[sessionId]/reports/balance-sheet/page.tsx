"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import {
  CurrencyField,
  DateField,
  ReportShell,
} from "@/components/reports/report-shell";
import { ReportView } from "@/components/reports/report-view";

export default function BalanceSheetPage() {
  const { sessionId: sid } = useParams<{ sessionId: string }>();
  const [asOf, setAsOf] = useState("");
  const [currency, setCurrency] = useState("");
  return (
    <ReportShell
      sid={sid}
      title="Balance Sheet"
      subtitle="Leave the date empty for today."
      anyOf={["report.financial"]}
    >
      <ReportView
        sid={sid}
        slug="balance-sheet"
        params={{ as_of: asOf, currency }}
        filters={
          <>
            <DateField label="As of" value={asOf} onChange={setAsOf} optional />
            <CurrencyField value={currency} onChange={setCurrency} allowAll />
          </>
        }
      />
    </ReportShell>
  );
}
