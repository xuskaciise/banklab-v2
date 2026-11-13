"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { formatMoney } from "@/lib/banking";
import { useSessionMe } from "@/lib/lab";
import { EmptyState } from "@/components/shared/empty-state";
import { StatusBadge } from "@/components/shared/status-badge";
import { QueryState, Table, Td, Th } from "@/components/lab/common";
import { ReportShell } from "@/components/reports/report-shell";

type Gl = components["schemas"]["GLAccountOut"];

export default function GlAccountsPage() {
  const { sessionId: sid } = useParams<{ sessionId: string }>();
  // Own-work-only viewers (always in exams) get the chart without bank-wide balances.
  const ownOnly = useSessionMe(sid).data?.visibility === "own";
  const q = useQuery({
    queryKey: ["gl-accounts", sid],
    queryFn: () => apiFetch<Gl[]>(`/api/s/${sid}/gl/accounts`),
  });
  return (
    <ReportShell
      sid={sid}
      title="Chart of accounts"
      subtitle={
        ownOnly
          ? "Chart of accounts. Bank-wide balances are hidden because this session shows your own work only."
          : "GL accounts with balances per currency. Open one to see its ledger lines."
      }
      anyOf={["gl.view"]}
    >
      <QueryState query={q}>
        {!q.data?.length ? (
          <EmptyState title="No GL accounts" description="This bank has no GL accounts yet." />
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Code</Th>
                <Th>Name</Th>
                <Th>Type</Th>
                {!ownOnly && <Th className="text-right">Balances</Th>}
                <Th>Ledger</Th>
              </tr>
            </thead>
            <tbody>
              {q.data.map((a) => (
                <tr key={a.id} className="hover:bg-hover">
                  <Td className="font-mono text-text-strong">{a.code}</Td>
                  <Td className={a.postable ? "text-text-strong" : "font-semibold text-text-strong"}>
                    {a.name}
                    {!a.is_active && (
                      <StatusBadge status="inactive" className="ml-2" />
                    )}
                  </Td>
                  <Td className="capitalize">{a.type}</Td>
                  {!ownOnly && (
                  <Td className="text-right tabular-nums">
                    {a.balances.length === 0
                      ? "-"
                      : a.balances.map((b) => (
                          <div key={b.currency}>{formatMoney(b.balance, b.currency)}</div>
                        ))}
                  </Td>
                  )}
                  <Td>
                    {a.postable && (
                      <Link
                        href={`/s/${sid}/gl/${a.id}`}
                        className="font-medium text-bank-primary hover:underline"
                      >
                        View ledger
                      </Link>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </QueryState>
    </ReportShell>
  );
}
