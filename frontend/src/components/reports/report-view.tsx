"use client";

import { useState } from "react";
import { Download, FileText, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorMsg, Loading } from "@/components/lab/common";
import { StatusBadge } from "@/components/shared/status-badge";
import {
  cellText,
  downloadReport,
  summaryText,
  useReport,
  type Report,
  type ReportParams,
} from "@/lib/reports";
import { cn } from "@/lib/utils";

const ROW_STYLE: Record<string, string> = {
  header: "bg-surface font-semibold text-text-strong",
  subtotal: "bg-hover font-medium text-text-strong",
  total:
    "border-t-2 border-text-strong bg-bank-sky-light font-semibold text-text-strong",
};

function Summary({ report }: { report: Report }) {
  if (!report.summary.length) return null;
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {report.summary.map((s) => {
        const diff = /difference$/i.test(s.label);
        const balanced = diff && Number(s.value) === 0;
        return (
          <div
            key={s.label}
            className="rounded-xl border border-border bg-card p-4 shadow-xs"
          >
            <p className="text-xs font-medium tracking-wide text-text-muted uppercase">
              {s.label}
            </p>
            <p className="mt-2 text-xl font-semibold text-text-strong tabular-nums">
              {summaryText(s.label, s.value, s.kind)}
            </p>
            {diff && (
              <div className="mt-2">
                <StatusBadge
                  status={balanced ? "completed" : "failed"}
                  label={balanced ? "Balanced" : "Unbalanced"}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

const isNum = (kind: string) => kind === "money" || kind === "int";

function SectionTable({ section }: { section: Report["sections"][number] }) {
  return (
    <section className="space-y-2">
      <h2 className="text-sm font-semibold text-text-strong">
        {section.title}
        {section.currency && (
          <span className="ml-2 font-normal text-text-muted">
            {section.currency}
          </span>
        )}
      </h2>
      <div className="overflow-x-auto rounded-xl border border-border bg-card shadow-xs">
        <table className="w-full min-w-max text-left text-sm text-text-body">
          <thead>
            <tr>
              {section.columns.map((c) => (
                <th
                  key={c.key}
                  className={cn(
                    "border-b border-border bg-surface px-4 py-2.5 text-xs font-medium tracking-wide whitespace-nowrap text-text-muted uppercase",
                    isNum(c.kind) && "text-right",
                  )}
                >
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {section.rows.length === 0 && (
              <tr>
                <td
                  colSpan={section.columns.length}
                  className="px-4 py-6 text-center text-text-muted"
                >
                  No rows for this selection.
                </td>
              </tr>
            )}
            {section.rows.map((r, i) => (
              <tr
                key={i}
                className={cn("hover:bg-hover", ROW_STYLE[String(r.style ?? "")])}
              >
                {section.columns.map((c) => (
                  <td
                    key={c.key}
                    className={cn(
                      "border-b border-border px-4 py-2.5",
                      isNum(c.kind) && "text-right tabular-nums",
                    )}
                  >
                    {cellText(r[c.key], c.kind, section.currency)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

/**
 * Generic report screen: filters slot, summary cards, section tables and
 * PDF/Excel downloads with the current filters. Pass `ready=false` while
 * required filters are missing.
 */
export function ReportView({
  sid,
  slug,
  params,
  ready = true,
  filters,
}: {
  sid: string;
  slug: string;
  params: ReportParams;
  ready?: boolean;
  filters?: React.ReactNode;
}) {
  const q = useReport(sid, slug, params, ready);
  const [busy, setBusy] = useState<string | null>(null);

  async function run(ext: ".pdf" | ".xlsx") {
    setBusy(ext);
    try {
      await downloadReport(sid, slug, ext, params);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Download failed");
    } finally {
      setBusy(null);
    }
  }
  const r = q.data;
  const disabled = !ready || !r || busy !== null;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-wrap items-end gap-3">{filters}</div>
        <div className="flex gap-2">
          <Button variant="outline" disabled={disabled} onClick={() => run(".pdf")}>
            {busy === ".pdf" ? <Loader2 className="animate-spin" /> : <FileText />}
            Download PDF
          </Button>
          <Button variant="outline" disabled={disabled} onClick={() => run(".xlsx")}>
            {busy === ".xlsx" ? <Loader2 className="animate-spin" /> : <Download />}
            Download Excel
          </Button>
        </div>
      </div>
      {!ready ? (
        <EmptyState
          title="Choose a filter"
          description="Select the required filter to run this report."
        />
      ) : q.isPending ? (
        <Loading label="Running report" />
      ) : q.isError || !r ? (
        <ErrorMsg error={q.error} />
      ) : (
        <>
          <p className="text-xs text-text-muted">
            {r.bank_name} - {r.branch} - {r.period} - generated{" "}
            {new Date(r.generated_at).toLocaleString("en-GB")} by {r.generated_by}
          </p>
          <Summary report={r} />
          {r.sections.length === 0 ? (
            <EmptyState title="No data" description="Nothing to report for this selection." />
          ) : (
            r.sections.map((s, i) => <SectionTable key={i} section={s} />)
          )}
        </>
      )}
    </div>
  );
}
