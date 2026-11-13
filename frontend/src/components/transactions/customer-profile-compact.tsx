"use client";

import { User } from "lucide-react";
import { formatAccountNo } from "@/lib/accounts";
import { formatMoney } from "@/lib/banking";
import { formatCif, useCustomer } from "@/lib/customers";
import type { AccountOut, PartyLink } from "@/lib/api/types";
import { StatusBadge } from "@/components/lab/common";
import { IdentityVerification, useIdentityImage } from "./identity-images";

function Item({ label, children }: { label: string; children: React.ReactNode }) {
  if (children === null || children === undefined || children === "") return null;
  return (
    <div className="min-w-0">
      <dt className="text-xs text-text-muted">{label}</dt>
      <dd className="text-sm font-medium break-words text-text-strong">{children}</dd>
    </div>
  );
}

function AvatarBox() {
  return (
    <span
      title="Photo not available"
      className="flex size-10 shrink-0 items-center justify-center rounded-full border border-dashed border-border bg-surface text-text-muted"
    >
      <User className="size-4" aria-hidden />
      <span className="sr-only">Photo not available</span>
    </span>
  );
}

function AvatarWithParty({ sid, cid, party }: { sid: string; cid: string; party: PartyLink }) {
  const { img } = useIdentityImage(sid, cid, party, "photo");
  return img.data ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={img.data}
      alt={`Photo of ${party.full_name}`}
      className="size-10 shrink-0 rounded-full border border-border object-cover object-top"
    />
  ) : (
    <AvatarBox />
  );
}

/** Dense account + customer preview for the one-screen transaction page. */
export function CustomerProfileCompact({ sid, account }: { sid: string; account: AccountOut }) {
  const q = useCustomer({ kind: "student", sessionId: sid }, account.customer_id);
  const c = q.data;
  const holder = c?.parties.find((p) => p.can_sign) ?? c?.parties[0];
  const doc = holder?.identity_documents[0];
  const opened = account.opened_at ? new Date(account.opened_at).toLocaleDateString() : "";

  return (
    <div className="space-y-3 rounded-lg border border-border bg-surface p-3">
      <div className="flex items-center gap-2.5">
        {holder ? (
          <AvatarWithParty sid={sid} cid={account.customer_id} party={holder} />
        ) : (
          <AvatarBox />
        )}
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-text-strong">{account.customer_name}</p>
          <p className="truncate font-mono text-xs text-text-body">
            {formatAccountNo(account.account_no)}
            {c && <span className="font-sans"> · CIF {formatCif(c.cif_no)}</span>}
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <StatusBadge status={account.status} />
          {c && (
            <StatusBadge
              status={c.kyc_complete ? "completed" : "pending"}
              label={c.kyc_complete ? "KYC complete" : "KYC incomplete"}
            />
          )}
        </div>
      </div>

      <div className="rounded-md border border-bank-accent/30 bg-bank-sky-light px-3 py-2">
        <p className="text-xs text-text-muted">Current balance</p>
        <p className="text-xl font-semibold text-bank-primary tabular-nums">
          {formatMoney(account.ledger_balance, account.currency)}
        </p>
      </div>

      <dl className="grid grid-cols-2 gap-x-3 gap-y-2">
        <Item label="Account no">
          <span className="font-mono">{formatAccountNo(account.account_no)}</span>
        </Item>
        <Item label="Product">{account.product_name}</Item>
        <Item label="Currency">{account.currency}</Item>
        <Item label="Opened">{opened}</Item>
      </dl>

      {q.isLoading && <p className="text-xs text-text-muted">Loading customer details…</p>}
      {q.isError && <p className="text-xs text-text-muted">Customer details are not available.</p>}
      {c && (
        <>
          <IdentityVerification
            sid={sid}
            customerId={account.customer_id}
            parties={c.parties}
            mandate={account.mandate}
            compact
          />
          <dl className="grid grid-cols-2 gap-x-3 gap-y-2 border-t border-border pt-3">
            <Item label="Sex">{holder?.sex}</Item>
            <Item label="Phone">{c.phone || holder?.phone}</Item>
            <Item label="ID number">{doc?.number}</Item>
            <Item label="Address">{c.address}</Item>
          </dl>
        </>
      )}
    </div>
  );
}
