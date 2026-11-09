"use client";

import { User } from "lucide-react";
import { formatAccountNo } from "@/lib/accounts";
import { formatMoney } from "@/lib/banking";
import { useCustomer } from "@/lib/customers";
import type { AccountOut, PartyLink } from "@/lib/api/types";
import { StatusBadge } from "@/components/lab/common";
import { IdentityVerification, useIdentityImage } from "./identity-images";

function Item({ label, children }: { label: string; children: React.ReactNode }) {
  if (children === null || children === undefined || children === "") return null;
  return (
    <div className="min-w-0">
      <dt className="text-xs text-text-muted">{label}</dt>
      <dd className="text-sm break-words text-text-body">
        {children}
      </dd>
    </div>
  );
}

function Thumb({
  sid,
  customerId,
  party,
}: {
  sid: string;
  customerId: string;
  party?: PartyLink;
}) {
  if (!party) return <ThumbBox />;
  return <ThumbWithParty sid={sid} customerId={customerId} party={party} />;
}

function ThumbWithParty({
  sid,
  customerId,
  party,
}: {
  sid: string;
  customerId: string;
  party: PartyLink;
}) {
  const { img } = useIdentityImage(sid, customerId, party, "photo");
  return img.data ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={img.data}
      alt={`Photo of ${party.full_name}`}
      className="h-16 w-14 shrink-0 rounded-lg border border-border bg-card object-cover"
    />
  ) : (
    <ThumbBox />
  );
}

function ThumbBox() {
  return (
    <div
      title="Photo not available"
      className="flex h-16 w-14 shrink-0 flex-col items-center justify-center rounded-lg border border-dashed border-border bg-card text-text-muted"
    >
      <User className="size-4" aria-hidden />
      <span className="sr-only">Photo not available</span>
    </div>
  );
}

/** Account + customer preview shown after a successful account lookup. */
export function CustomerProfile({ sid, account }: { sid: string; account: AccountOut }) {
  const q = useCustomer({ kind: "student", sessionId: sid }, account.customer_id);
  const c = q.data;
  const holder = c?.parties.find((p) => p.can_sign) ?? c?.parties[0];
  const doc = holder?.identity_documents[0];
  const opened = account.opened_at
    ? new Date(account.opened_at).toLocaleDateString()
    : "";

  return (
    <div className="space-y-4 rounded-xl border border-border bg-surface p-4">
      <div className="flex items-start gap-3">
        <Thumb sid={sid} customerId={account.customer_id} party={holder} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-base font-semibold text-text-strong">
            {account.customer_name}
          </p>
          <p className="font-mono text-xs text-text-muted">
            {formatAccountNo(account.account_no)}
            {c && <span className="font-sans"> · CIF {c.cif_no}</span>}
          </p>
          {doc && (
            <p className="text-xs text-text-muted">
              {doc.type.replace(/_/g, " ")}: {doc.number}
            </p>
          )}
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1.5">
          <StatusBadge status={account.status} />
          {c && (
            <StatusBadge
              status={c.kyc_complete ? "completed" : "pending"}
              label={c.kyc_complete ? "KYC complete" : "KYC incomplete"}
            />
          )}
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card p-3">
        <p className="text-xs text-text-muted">Current balance</p>
        <p className="text-2xl font-semibold text-text-strong tabular-nums">
          {formatMoney(account.ledger_balance, account.currency)}
        </p>
      </div>

      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Item label="Account no">
          <span className="font-mono">{formatAccountNo(account.account_no)}</span>
        </Item>
        <Item label="Product">{account.product_name}</Item>
        <Item label="Currency">{account.currency}</Item>
        <Item label="Opened">{opened}</Item>
      </dl>

      {q.isLoading && (
        <p className="border-t border-border pt-3 text-sm text-text-muted">
          Loading customer details…
        </p>
      )}
      {q.isError && (
        <p className="border-t border-border pt-3 text-sm text-text-muted">
          Customer details are not available.
        </p>
      )}
      {c && (
        <>
          <IdentityVerification
            sid={sid}
            customerId={account.customer_id}
            parties={c.parties}
            mandate={account.mandate}
          />
          <section className="space-y-2 border-t border-border pt-4">
            <h4 className="text-sm font-semibold text-text-strong">
              Customer Details
            </h4>
            <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Item label="Name">{c.display_name}</Item>
              <Item label="Sex">{holder?.sex}</Item>
              <Item label="Phone">{c.phone || holder?.phone}</Item>
              <Item label="Email">{c.email}</Item>
              <Item label="Address">{c.address}</Item>
              <Item label="ID number">{doc?.number}</Item>
            </dl>
          </section>
        </>
      )}
    </div>
  );
}
