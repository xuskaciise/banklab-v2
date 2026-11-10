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

export default function GlLedgerPage() {
  const { sessionId: sid, accountId } = useParams<{
    sessionId: string;
    accountId: string;
  }>();
  const [currency, setCurrency] = useState("USD");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const err = rangeError(from, to);
  return (
    <ReportShell
      sid={sid}
      title="GL ledger"
      subtitle="Ledger lines of one GL account in one currency."
      anyOf={["gl.view"]}
      back={{ href: `/s/${sid}/gl`, label: "Chart of accounts" }}
    >
      {err && <ErrorMsg error={new Error(err)} />}
      <ReportView
        sid={sid}
        slug="gl-ledger"
        ready={!err}
        params={{ gl_account_id: accountId, currency, date_from: from, date_to: to }}
        filters={
          <>
            <CurrencyField value={currency} onChange={setCurrency} />
            <DateField label="From" value={from} onChange={setFrom} optional />
            <DateField label="To" value={to} onChange={setTo} optional />
          </>
        }
      />
    </ReportShell>
  );
}
