"use client";

import { useState } from "react";
import { BookOpenCheck } from "lucide-react";
import { CHEQUE_STATUS_LABEL, useChequebooks, useCheques } from "@/lib/cheques";
import { formatDateTime } from "@/lib/lab";
import type { AccountOut } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/shared/empty-state";
import { StatusBadge } from "@/components/shared/status-badge";
import { ErrorMsg, Loading, Select, Table, Td, Th } from "@/components/lab/common";
import { IssueChequebookDialog, StopChequeDialog } from "./cheque-dialogs";

const CHEQUE_TONE = { issued: "info", paid: "success", stopped: "danger" } as const;

/** Cheques card on the account page: chequebooks + cheque leaves. */
export function AccountCheques({
  sid,
  account,
  canIssue,
  canStop,
}: {
  sid: string;
  account: AccountOut;
  canIssue: boolean;
  canStop: boolean;
}) {
  const aid = account.id;
  const [status, setStatus] = useState("");
  const [issuing, setIssuing] = useState(false);
  const [stopping, setStopping] = useState<{ id: string; number: number } | null>(null);
  const books = useChequebooks(sid, aid);
  const cheques = useCheques(sid, aid, status);
  const active = account.status === "active";

  return (
    <Card className="gap-4 px-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-base font-semibold text-text-strong">
          <BookOpenCheck className="size-4 text-bank-primary" aria-hidden /> Cheques
        </h2>
        {canIssue && active && (
          <Button onClick={() => setIssuing(true)}>Issue chequebook</Button>
        )}
      </div>

      <div className="space-y-2">
        <h3 className="text-sm font-medium text-text-strong">Chequebooks</h3>
        {books.isPending ? (
          <Loading label="Loading chequebooks" />
        ) : books.isError ? (
          <ErrorMsg error={books.error} />
        ) : books.data.length === 0 ? (
          <EmptyState
            title="No chequebooks"
            description="No chequebook has been issued for this account."
          />
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Series</Th>
                <Th className="text-right">Leaves</Th>
                <Th>Issued by</Th>
                <Th>Issued at</Th>
              </tr>
            </thead>
            <tbody>
              {books.data.map((b) => (
                <tr key={b.id} className="hover:bg-hover">
                  <Td className="font-mono">
                    {b.first_no} – {b.last_no}
                  </Td>
                  <Td className="text-right tabular-nums">{b.leaves}</Td>
                  <Td>{b.issued_by_name}</Td>
                  <Td>{formatDateTime(b.issued_at)}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </div>

      <div className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-medium text-text-strong">Cheques</h3>
          <Select
            aria-label="Filter cheques by status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">All statuses</option>
            {Object.entries(CHEQUE_STATUS_LABEL).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </Select>
        </div>
        {cheques.isPending ? (
          <Loading label="Loading cheques" />
        ) : cheques.isError ? (
          <ErrorMsg error={cheques.error} />
        ) : cheques.data.length === 0 ? (
          <EmptyState
            title="No cheques"
            description={
              status ? "No cheques match this status." : "Issue a chequebook to create cheques."
            }
          />
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Cheque no</Th>
                <Th>Status</Th>
                <Th>Stop reason</Th>
                <Th />
              </tr>
            </thead>
            <tbody>
              {cheques.data.map((c) => (
                <tr key={c.id} className="hover:bg-hover">
                  <Td className="font-mono">{c.number}</Td>
                  <Td>
                    <StatusBadge
                      status={c.status}
                      label={CHEQUE_STATUS_LABEL[c.status] ?? c.status}
                      tone={CHEQUE_TONE[c.status as keyof typeof CHEQUE_TONE]}
                    />
                  </Td>
                  <Td className="text-text-muted">
                    {c.status === "stopped" ? c.stop_reason : ""}
                  </Td>
                  <Td className="text-right">
                    {canStop && c.status === "issued" && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setStopping({ id: c.id, number: c.number })}
                      >
                        Stop
                      </Button>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </div>

      {issuing && (
        <IssueChequebookDialog sid={sid} aid={aid} onClose={() => setIssuing(false)} />
      )}
      {stopping && (
        <StopChequeDialog
          sid={sid}
          aid={aid}
          cheque={stopping}
          onClose={() => setStopping(null)}
        />
      )}
    </Card>
  );
}
