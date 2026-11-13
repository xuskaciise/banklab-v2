"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { Select } from "@/components/ui/input";
import { Labeled } from "@/components/lab/common";
import {
  CurrencyField,
  DateField,
  ReportShell,
} from "@/components/reports/report-shell";
import { ReportView } from "@/components/reports/report-view";
import { STATUS_LABEL, TYPE_LABEL } from "@/lib/transactions";

function Choice({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: Record<string, string>;
}) {
  return (
    <Labeled label={label}>
      <Select value={value} onChange={(e) => onChange(e.target.value)} className="w-48">
        <option value="">All</option>
        {Object.entries(options).map(([k, v]) => (
          <option key={k} value={k}>
            {v}
          </option>
        ))}
      </Select>
    </Labeled>
  );
}

export default function JournalPage() {
  const { sessionId: sid } = useParams<{ sessionId: string }>();
  const [date, setDate] = useState("");
  const [type, setType] = useState("");
  const [status, setStatus] = useState("");
  const [currency, setCurrency] = useState("");
  return (
    <ReportShell
      sid={sid}
      title="Transaction Journal"
      subtitle="All transactions of one business day. Leave the date empty for the current business date."
      anyOf={["report.operational"]}
    >
      <ReportView
        sid={sid}
        slug="journal"
        params={{ business_date: date, type, status, currency }}
        filters={
          <>
            <DateField label="Business date" value={date} onChange={setDate} optional />
            <Choice label="Type" value={type} onChange={setType} options={TYPE_LABEL} />
            <Choice label="Status" value={status} onChange={setStatus} options={STATUS_LABEL} />
            <CurrencyField value={currency} onChange={setCurrency} allowAll />
          </>
        }
      />
    </ReportShell>
  );
}
