"use client";

import { useParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { useSessionMe } from "@/lib/lab";
import { useCashTransfers, useVault } from "@/lib/banking";
import { EmptyState } from "@/components/shared/empty-state";
import { QueryState, ReadOnlyBanner } from "@/components/lab/common";
import { TransfersPanel } from "@/components/vault/transfers-panel";
import { ReconAlert, ReconCard, VaultCash, VaultHeader } from "@/components/vault/vault-top";

export default function VaultPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const me = useSessionMe(sessionId);
  const perms = new Set(me.data?.permissions.map((p) => p.code));
  // Own-work-only viewers (always in exams) get 403 from the bank-wide vault API.
  const ownOnly = me.data?.visibility === "own";
  const canView = perms.has("vault.view") && !ownOnly;
  const vault = useVault(sessionId, canView);
  const transfers = useCashTransfers(sessionId, canView);
  const qc = useQueryClient();
  const readOnly = !!me.data?.read_only;

  return (
    <div className="w-full space-y-4 p-6">
      <VaultHeader
        vault={vault.data}
        updatedAt={Math.max(vault.dataUpdatedAt, transfers.dataUpdatedAt)}
        fetching={vault.isFetching || transfers.isFetching}
        onRefresh={() => {
          qc.invalidateQueries({ queryKey: ["vault", sessionId] });
          qc.invalidateQueries({ queryKey: ["cash-transfers", sessionId] });
        }}
      />
      <QueryState query={me}>
        {readOnly && <ReadOnlyBanner />}
        {ownOnly ? (
          <EmptyState title="Not available in this session" description="This session shows your own work only. The bank-wide vault is not available here." />
        ) : !canView ? (
          <EmptyState title="No access" description="Your role cannot view the vault." />
        ) : (
          <>
            <ReconAlert vault={vault.data} />
            <VaultCash vault={vault.data} loading={vault.isPending} />
            {vault.isError && <p className="text-sm text-fin-danger">{vault.error.message}</p>}
            <ReconCard vault={vault.data} />
            <TransfersPanel
              sid={sessionId}
              rows={transfers.data ?? []}
              loading={transfers.isPending}
              error={transfers.error}
              has={(c) => perms.has(c)}
              readOnly={readOnly}
            />
          </>
        )}
      </QueryState>
    </div>
  );
}
