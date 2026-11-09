"use client";

import { ImageIcon } from "lucide-react";
import { useBlobUrl, useCustomer } from "@/lib/customers";
import type { PartyLink } from "@/lib/api/types";

const MANDATE_LABEL: Record<string, string> = {
  any_one: "Any one may sign",
  all_jointly: "All must sign jointly",
};

function Pic({
  sid,
  customerId,
  party,
  kind,
}: {
  sid: string;
  customerId: string;
  party: PartyLink;
  kind: "photo" | "signature";
}) {
  const has = kind === "photo" ? party.has_photo : party.has_signature;
  const path = `/api/s/${sid}/customers/${customerId}/parties/${party.party_id}/${kind}`;
  const img = useBlobUrl(path, has, 0);
  const title = kind === "photo" ? "Photo" : "Signature";
  const size = kind === "photo" ? "h-24 w-20" : "h-16 w-40";
  return (
    <figure className="space-y-1">
      <div
        className={`${size} flex items-center justify-center overflow-hidden rounded-md border border-border bg-card`}
      >
        {img.data ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={img.data}
            alt={`${title} of ${party.full_name}`}
            className="size-full object-contain"
          />
        ) : (
          <span className="flex flex-col items-center gap-1 px-1 text-center text-xs text-text-muted">
            <ImageIcon className="size-4" aria-hidden />
            {!has ? `No ${kind}` : img.isError ? "Unavailable" : "Loading…"}
          </span>
        )}
      </div>
      <figcaption className="text-xs text-text-muted">{title}</figcaption>
    </figure>
  );
}

/** Photo and specimen signature of everyone who may sign on the account. */
export function CustomerIdentity({
  sid,
  customerId,
  mandate,
}: {
  sid: string;
  customerId: string;
  mandate?: string;
}) {
  const q = useCustomer({ kind: "student", sessionId: sid }, customerId);
  if (q.isLoading)
    return <p className="text-sm text-text-muted">Loading photo and signature…</p>;
  if (q.isError || !q.data)
    return (
      <p className="text-sm text-text-muted">
        Photo and signature are not available.
      </p>
    );
  const signers = q.data.parties.filter((p) => p.can_sign);
  const shown = signers.length ? signers : q.data.parties;
  return (
    <div className="space-y-3 border-t border-border pt-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-xs font-medium tracking-wide text-text-muted uppercase">
          Verify the customer
        </p>
        {shown.length > 1 && mandate && (
          <p className="text-xs text-text-body">
            {MANDATE_LABEL[mandate] ?? mandate}
          </p>
        )}
      </div>
      {shown.map((p) => (
        <div key={p.party_id} className="space-y-2">
          {shown.length > 1 && (
            <p className="text-sm font-medium text-text-strong">{p.full_name}</p>
          )}
          <div className="flex flex-wrap items-end gap-3">
            <Pic sid={sid} customerId={customerId} party={p} kind="photo" />
            <Pic sid={sid} customerId={customerId} party={p} kind="signature" />
          </div>
        </div>
      ))}
    </div>
  );
}
