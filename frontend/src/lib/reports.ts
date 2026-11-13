"use client";

import { useQuery } from "@tanstack/react-query";
import { apiBlob, apiFetch } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { formatMoney } from "@/lib/banking";

export type Report = components["schemas"]["ReportOut"];
export type ReportParams = Record<string, string | undefined>;

export type ReportMeta = {
  slug: string;
  title: string;
  description: string;
  perm: string;
};

/** Reports listed on the index, with the permission each one needs. */
export const REPORTS: ReportMeta[] = [
  { slug: "trial-balance", title: "Trial Balance", description: "Debits and credits per GL account and currency.", perm: "report.financial" },
  { slug: "balance-sheet", title: "Balance Sheet", description: "Assets, liabilities and equity per currency.", perm: "report.financial" },
  { slug: "income-statement", title: "Income Statement", description: "Income and expenses for a date range.", perm: "report.financial" },
  { slug: "journal", title: "Transaction Journal", description: "All transactions of a business day, with filters.", perm: "report.operational" },
  { slug: "teller-cash", title: "Teller Cash Report", description: "Cash position of one teller session.", perm: "report.operational" },
  { slug: "branch-daily", title: "Branch Daily Report", description: "Daily totals and vault position.", perm: "report.operational" },
];

/** Reports whose route slug differs from the API slug. */
const API_SLUG: Record<string, string> = { journal: "transaction-journal" };

export const REPORT_PERMS = [
  "report.operational",
  "report.financial",
  "gl.view",
  "account.statement",
];

function url(sid: string, slug: string, ext: "" | ".pdf" | ".xlsx", params: ReportParams) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v) qs.set(k, v);
  const q = qs.toString();
  return `/api/s/${sid}/reports/${API_SLUG[slug] ?? slug}${ext}${q ? `?${q}` : ""}`;
}

export const useReport = (
  sid: string,
  slug: string,
  params: ReportParams,
  enabled: boolean,
) =>
  useQuery({
    queryKey: ["report", sid, slug, params],
    queryFn: () => apiFetch<Report>(url(sid, slug, "", params)),
    enabled,
  });

/** PDF opens inline in a new tab; Excel is saved. Both use the session cookie. */
export async function downloadReport(
  sid: string,
  slug: string,
  ext: ".pdf" | ".xlsx",
  params: ReportParams,
) {
  const win = ext === ".pdf" ? window.open("", "_blank") : null;
  try {
    const blob = await apiBlob(url(sid, slug, ext, params));
    const href = URL.createObjectURL(blob);
    if (ext === ".pdf") {
      if (win) win.location.href = href;
      else window.location.href = href;
    } else {
      const a = document.createElement("a");
      a.href = href;
      a.download = `${slug}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    }
    setTimeout(() => URL.revokeObjectURL(href), 60_000);
  } catch (e) {
    win?.close();
    throw e;
  }
}

function plain(value: unknown) {
  return formatMoney(String(value), "").trim();
}

/** Display-only formatting of an API cell value. */
export function cellText(value: unknown, kind: string, currency: string): string {
  if (value === null || value === undefined || value === "") return "";
  if (kind === "money") return currency ? formatMoney(String(value), currency) : plain(value);
  return String(value);
}

/** Summary money values carry no currency; take it from a leading "USD ..." label. */
export function summaryText(label: string, value: string, kind: string): string {
  if (kind !== "money") return value;
  const cur = /^([A-Z]{3})\b/.exec(label)?.[1] ?? "";
  return cur ? formatMoney(value, cur) : plain(value);
}

export const todayIso = () => new Date().toISOString().slice(0, 10);
