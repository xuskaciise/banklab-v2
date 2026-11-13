"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus, Search, Wallet } from "lucide-react";
import { ACCOUNT_PAGE_SIZE, formatAccountNo, statusLabel, useAccounts } from "@/lib/accounts";
import { formatMoney } from "@/lib/banking";
import { formatCif } from "@/lib/customers";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/shared/empty-state";
import { Pagination } from "@/components/shared/pagination";
import { StatusBadge } from "@/components/shared/status-badge";
import { ErrorMsg, Loading, Select, Table, Td, Th } from "@/components/lab/common";
import { OpenAccountDialog } from "@/components/accounts/open-account-dialog";

export function AccountsList({
  sessionId,
  canOpen,
}: {
  sessionId: string;
  canOpen: boolean;
}) {
  const router = useRouter();
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [opening, setOpening] = useState(false);
  const list = useAccounts(sessionId, { status, q: q.trim(), page });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative w-full sm:w-80">
          <Search className="pointer-events-none absolute top-2.5 left-3 size-4 text-text-muted" />
          <Input
            aria-label="Search accounts"
            placeholder="Account no, name, phone or ID number"
            className="h-9 pl-9"
            value={q}
            onChange={(e) => {
              setPage(1);
              setQ(e.target.value);
            }}
          />
        </div>
        <Select
          aria-label="Account status"
          className="h-9"
          value={status}
          onChange={(e) => {
            setPage(1);
            setStatus(e.target.value);
          }}
        >
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="closed">Closed</option>
        </Select>
        {canOpen && (
          <Button className="ml-auto" onClick={() => setOpening(true)}>
            <Plus /> Open account
          </Button>
        )}
      </div>
      {list.isPending ? (
        <Loading label="Loading accounts" />
      ) : list.isError ? (
        <ErrorMsg error={list.error} />
      ) : list.data.items.length === 0 ? (
        <EmptyState
          icon={Wallet}
          title={status || q ? "No matching accounts" : "No accounts yet"}
          description={
            status || q
              ? "Try a different search or filter."
              : "Accounts opened in this bank will appear here."
          }
        />
      ) : (
        <>
          <Table>
            <thead>
              <tr>
                <Th>Account no</Th>
                <Th>Customer</Th>
                <Th>Product</Th>
                <Th>Currency</Th>
                <Th className="text-right">Balance</Th>
                <Th>Status</Th>
              </tr>
            </thead>
            <tbody>
              {list.data.items.map((a) => (
                <tr key={a.id} className="hover:bg-hover">
                  <Td className="font-mono text-xs">
                    <Link
                      href={`/s/${sessionId}/accounts/${a.id}`}
                      className="font-medium text-bank-primary hover:underline"
                    >
                      {formatAccountNo(a.account_no)}
                    </Link>
                  </Td>
                  <Td>
                    <span className="font-medium text-text-strong">
                      {a.customer_name}
                    </span>{" "}
                    <span className="font-mono text-xs text-text-muted">
                      CIF {formatCif(a.cif_no)}
                    </span>
                  </Td>
                  <Td>{a.product_name}</Td>
                  <Td>{a.currency}</Td>
                  <Td className="text-right font-medium whitespace-nowrap text-text-strong tabular-nums">
                    {formatMoney(a.ledger_balance, a.currency)}
                  </Td>
                  <Td>
                    <StatusBadge status={a.status} label={statusLabel(a.status)} />
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
          <Pagination
            page={page}
            pageSize={ACCOUNT_PAGE_SIZE}
            total={list.data.count}
            onPageChange={setPage}
          />
        </>
      )}
      {opening && (
        <OpenAccountDialog
          sessionId={sessionId}
          onClose={() => setOpening(false)}
          onOpened={(a) => router.push(`/s/${sessionId}/accounts/${a.id}`)}
        />
      )}
    </div>
  );
}
