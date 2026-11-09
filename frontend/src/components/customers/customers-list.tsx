"use client";

import { useState } from "react";
import Link from "next/link";
import { Plus, Search, Users } from "lucide-react";
import {
  PAGE_SIZE,
  CUSTOMER_TYPES,
  formatCif,
  typeLabel,
  useCustomers,
  type CustomerScope,
} from "@/lib/customers";
import { formatDateTime } from "@/lib/lab";
import { buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/shared/empty-state";
import { Pagination } from "@/components/shared/pagination";
import { StatusBadge } from "@/components/shared/status-badge";
import {
  ErrorMsg,
  Loading,
  Select,
  Table,
  Td,
  Th,
} from "@/components/lab/common";

export function CustomersList({
  scope,
  hrefFor,
  newHref,
  enabled = true,
}: {
  scope: CustomerScope;
  hrefFor: (id: string) => string;
  /** Pass only when the user may create customers. */
  newHref?: string;
  enabled?: boolean;
}) {
  const [text, setText] = useState("");
  const [q, setQ] = useState("");
  const [type, setType] = useState("");
  const [page, setPage] = useState(1);
  const list = useCustomers(scope, { q, type, page }, enabled);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <form
          role="search"
          className="relative min-w-56 flex-1 sm:max-w-sm"
          onSubmit={(e) => {
            e.preventDefault();
            setPage(1);
            setQ(text.trim());
          }}
        >
          <Search className="pointer-events-none absolute top-2.5 left-3 size-4 text-text-muted" />
          <Input
            aria-label="Search customers"
            placeholder="Search name, phone or CIF…"
            className="h-9 pl-9"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </form>
        <Select
          aria-label="Customer type"
          className="h-9"
          value={type}
          onChange={(e) => {
            setPage(1);
            setType(e.target.value);
          }}
        >
          <option value="">All types</option>
          {CUSTOMER_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </Select>
        {newHref && (
          <Link href={newHref} className={buttonVariants({ className: "ml-auto" })}>
            <Plus /> New customer
          </Link>
        )}
      </div>
      {list.isPending ? (
        <Loading label="Loading customers" />
      ) : list.isError ? (
        <ErrorMsg error={list.error} />
      ) : list.data.items.length === 0 ? (
        <EmptyState
          icon={Users}
          title={q || type ? "No matching customers" : "No customers yet"}
          description={
            q || type
              ? "Try a different search or filter."
              : "Customers added to this bank will appear here."
          }
        />
      ) : (
        <>
          <Table>
            <thead>
              <tr>
                <Th>CIF</Th>
                <Th>Name</Th>
                <Th>Type</Th>
                <Th>KYC</Th>
                <Th>Phone</Th>
                <Th>Created</Th>
              </tr>
            </thead>
            <tbody>
              {list.data.items.map((c) => (
                <tr key={c.id} className="hover:bg-hover">
                  <Td className="font-mono text-xs text-text-muted">
                    {formatCif(c.cif_no)}
                  </Td>
                  <Td>
                    <Link
                      href={hrefFor(c.id)}
                      className="font-medium text-bank-primary hover:underline"
                    >
                      {c.display_name}
                    </Link>
                  </Td>
                  <Td>
                    <StatusBadge status={c.type} label={typeLabel(c.type)} tone="info" />
                  </Td>
                  <Td>
                    <StatusBadge
                      status={c.kyc_complete ? "kyc_complete" : "kyc_incomplete"}
                      label={c.kyc_complete ? "Complete" : "Incomplete"}
                      tone={c.kyc_complete ? "success" : "pending"}
                    />
                  </Td>
                  <Td>{c.phone || "—"}</Td>
                  <Td className="whitespace-nowrap tabular-nums">
                    {formatDateTime(c.created_at)}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
          <Pagination
            page={page}
            pageSize={PAGE_SIZE}
            total={list.data.count}
            onPageChange={setPage}
          />
        </>
      )}
    </div>
  );
}
