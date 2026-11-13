"use client";

import { useState } from "react";
import type { SessionOut } from "@/lib/api/types";
import { useBanks } from "@/lib/lab";
import { EmptyState } from "@/components/shared/empty-state";
import { QueryState, Select } from "@/components/lab/common";
import { CustomersList } from "@/components/customers/customers-list";

/** Instructor: read-only customer list for one bank at a time. */
export function CustomersTab({ session }: { session: SessionOut }) {
  const banks = useBanks(session.id);
  const [bankId, setBankId] = useState("");
  const current = bankId || banks.data?.[0]?.id || "";
  return (
    <div className="space-y-4">
      <QueryState query={banks}>
        {banks.data?.length ? (
          <>
            <div className="flex items-center gap-2">
              <span className="text-sm text-text-muted">Bank</span>
              <Select
                aria-label="Bank"
                className="h-9"
                value={current}
                onChange={(e) => setBankId(e.target.value)}
              >
                {banks.data.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </Select>
            </div>
            <CustomersList
              key={current}
              scope={{ kind: "staff", sessionId: session.id, bankId: current }}
              hrefFor={(cid) =>
                `/instructor/sessions/${session.id}/banks/${current}/customers/${cid}`
              }
            />
          </>
        ) : (
          <EmptyState
            title="No banks yet"
            description="Banks are created when the session is opened."
          />
        )}
      </QueryState>
    </div>
  );
}
