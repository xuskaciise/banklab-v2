"use client";

import { useState } from "react";
import { ImageIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { useBlobUrl } from "@/lib/customers";
import type { PartyLink } from "@/lib/api/types";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export const MANDATE_LABEL: Record<string, string> = {
  any_one: "Any one may sign",
  all_jointly: "All must sign jointly",
};

export function useIdentityImage(
  sid: string,
  customerId: string,
  party: PartyLink,
  kind: "photo" | "signature",
) {
  const has = kind === "photo" ? party.has_photo : party.has_signature;
  const path = `/api/s/${sid}/customers/${customerId}/parties/${party.party_id}/${kind}`;
  return { has, img: useBlobUrl(path, has, 0) };
}

/** Photo or signature tile; fixed size so a missing image never shifts layout. */
export function IdentityImage({
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
  const [open, setOpen] = useState(false);
  const { has, img } = useIdentityImage(sid, customerId, party, kind);
  const title = kind === "photo" ? "Photo" : "Signature";
  const alt = `${title} of ${party.full_name}`;
  const box = kind === "photo" ? "h-32 w-24" : "h-20 w-44 sm:w-52";
  return (
    <figure className="space-y-1.5">
      {img.data ? (
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label={`Enlarge ${alt}`}
          className={cn(
            box,
            "overflow-hidden rounded-lg border border-border bg-card outline-none transition-colors hover:border-bank-accent focus-visible:ring-2 focus-visible:ring-bank-accent",
          )}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={img.data} alt={alt} className="size-full object-contain" />
        </button>
      ) : (
        <div
          className={cn(
            box,
            "flex flex-col items-center justify-center gap-1 rounded-lg border border-dashed border-border bg-surface px-2 text-center text-xs text-text-muted",
          )}
        >
          <ImageIcon className="size-4" aria-hidden />
          {!has
            ? `${title} not available`
            : img.isError
              ? `${title} unavailable`
              : "Loading…"}
        </div>
      )}
      <figcaption className="text-xs text-text-muted">{title}</figcaption>
      {img.data && (
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{alt}</DialogTitle>
            </DialogHeader>
            <DialogBody>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={img.data}
                alt={alt}
                className="mx-auto max-h-[70vh] max-w-full rounded-lg border border-border object-contain"
              />
            </DialogBody>
          </DialogContent>
        </Dialog>
      )}
    </figure>
  );
}

/** One row per signer (name + mandate label for joint accounts). */
export function IdentityVerification({
  sid,
  customerId,
  parties,
  mandate,
}: {
  sid: string;
  customerId: string;
  parties: PartyLink[];
  mandate?: string;
}) {
  const signers = parties.filter((p) => p.can_sign);
  const shown = signers.length ? signers : parties;
  if (!shown.length) return null;
  return (
    <section className="space-y-3 border-t border-border pt-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h4 className="text-sm font-semibold text-text-strong">
          Identity Verification
        </h4>
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
          <div className="flex flex-wrap items-end gap-4">
            <IdentityImage sid={sid} customerId={customerId} party={p} kind="photo" />
            <IdentityImage
              sid={sid}
              customerId={customerId}
              party={p}
              kind="signature"
            />
          </div>
        </div>
      ))}
    </section>
  );
}
