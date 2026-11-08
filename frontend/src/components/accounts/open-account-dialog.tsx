"use client";

import { useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Search } from "lucide-react";
import { MANDATES, kycMissingFrom, useOpenAccount, useProducts } from "@/lib/accounts";
import { formatCif, typeLabel, useCustomer, useCustomers } from "@/lib/customers";
import type { AccountOut, KycItem } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ErrorMsg, Labeled, Loading, Select } from "@/components/lab/common";
import { cn } from "@/lib/utils";

function KycList({
  items,
  sessionId,
  customerId,
}: {
  items: KycItem[];
  sessionId: string;
  customerId: string;
}) {
  return (
    <div
      role="alert"
      className="space-y-2 rounded-lg border border-border bg-fin-pending-bg p-3"
    >
      <p className="text-sm font-semibold text-fin-pending">
        KYC incomplete: an account cannot be opened until these are added
      </p>
      <ul className="list-disc space-y-1 pl-5 text-sm text-text-body">
        {items.map((m) => (
          <li key={`${m.code}-${m.party_id ?? "customer"}`}>{m.label}</li>
        ))}
      </ul>
      <Link
        href={`/s/${sessionId}/customers/${customerId}`}
        className="text-sm font-medium text-bank-primary hover:underline"
      >
        Go to customer page
      </Link>
    </div>
  );
}

export function OpenAccountDialog({
  sessionId,
  customerId: presetCustomerId,
  onClose,
  onOpened,
}: {
  sessionId: string;
  /** Prefilled customer (from the customer page). */
  customerId?: string;
  onClose: () => void;
  onOpened?: (a: AccountOut) => void;
}) {
  const [customerId, setCustomerId] = useState(presetCustomerId ?? "");
  const [text, setText] = useState("");
  const [productId, setProductId] = useState("");
  const [mandate, setMandate] = useState("any_one");
  const [localError, setLocalError] = useState<string | null>(null);

  const search = useCustomers(
    { kind: "student", sessionId },
    { q: text.trim(), type: "", page: 1 },
    !presetCustomerId,
  );
  const customer = useCustomer(
    { kind: "student", sessionId },
    customerId,
    !!customerId,
  );
  const products = useProducts(sessionId);
  const open = useOpenAccount(sessionId);

  const c = customerId ? customer.data : undefined;
  const product = products.data?.find((p) => p.id === productId);
  const needsMandate = !!c && c.type !== "individual";
  const kycBlocked = !!c && !c.kyc_complete;
  const serverKyc = kycMissingFrom(open.error);

  function submit() {
    if (!customerId) return setLocalError("Choose a customer");
    if (!productId) return setLocalError("Choose a product");
    setLocalError(null);
    open.mutate(
      {
        customer_id: customerId,
        product_id: productId,
        mandate: needsMandate ? mandate : "any_one",
      },
      {
        onSuccess: (a) => {
          toast.success(`Account ${a.account_no} opened`);
          onOpened?.(a);
          onClose();
        },
      },
    );
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <form
          noValidate
          className="flex min-h-0 flex-col"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <DialogHeader>
            <DialogTitle>Open account</DialogTitle>
          </DialogHeader>
          <DialogBody className="space-y-4">
            {presetCustomerId ? (
              customer.isPending ? (
                <Loading label="Loading customer" />
              ) : c ? (
                <p className="text-sm">
                  <span className="text-text-muted">Customer: </span>
                  <span className="font-medium text-text-strong">
                    {c.display_name}
                  </span>{" "}
                  <span className="font-mono text-xs text-text-muted">
                    CIF {formatCif(c.cif_no)}
                  </span>
                </p>
              ) : (
                <ErrorMsg error={customer.error} />
              )
            ) : (
              <div className="space-y-2">
                <span className="text-sm font-medium text-text-strong">Customer</span>
                <div className="relative">
                  <Search className="pointer-events-none absolute top-2.5 left-3 size-4 text-text-muted" />
                  <Input
                    aria-label="Search customers"
                    placeholder="Search name, phone or CIF…"
                    className="pl-9"
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") e.preventDefault();
                    }}
                  />
                </div>
                <ul
                  aria-label="Customer results"
                  className="max-h-44 divide-y divide-border overflow-y-auto rounded-lg border border-border"
                >
                  {search.isPending ? (
                    <li className="p-3 text-sm text-text-muted">Loading…</li>
                  ) : search.data?.items.length ? (
                    search.data.items.map((x) => (
                      <li key={x.id}>
                        <button
                          type="button"
                          aria-pressed={x.id === customerId}
                          onClick={() => setCustomerId(x.id)}
                          className={cn(
                            "flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-hover",
                            x.id === customerId && "bg-bank-sky-light",
                          )}
                        >
                          <span className="font-medium text-text-strong">
                            {x.display_name}
                          </span>
                          <span className="font-mono text-xs text-text-muted">
                            CIF {formatCif(x.cif_no)} · {typeLabel(x.type)}
                          </span>
                        </button>
                      </li>
                    ))
                  ) : (
                    <li className="p-3 text-sm text-text-muted">
                      No matching customers
                    </li>
                  )}
                </ul>
                {c && (
                  <p className="text-sm text-text-body">
                    Selected:{" "}
                    <span className="font-medium text-text-strong">
                      {c.display_name}
                    </span>
                  </p>
                )}
              </div>
            )}

            {kycBlocked && c && (
              <KycList items={c.kyc_missing} sessionId={sessionId} customerId={c.id} />
            )}

            <Labeled label="Product">
              <Select
                className="w-full"
                value={productId}
                onChange={(e) => setProductId(e.target.value)}
                disabled={products.isPending}
              >
                <option value="">
                  {products.isPending ? "Loading products…" : "Choose a product"}
                </option>
                {products.data?.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.currency})
                  </option>
                ))}
              </Select>
            </Labeled>
            {product && (
              <p className="text-xs text-text-muted">Currency: {product.currency}</p>
            )}
            <ErrorMsg error={products.error} />

            {needsMandate && (
              <Labeled label="Signing mandate" hint="Who may operate this account.">
                <Select
                  className="w-full"
                  value={mandate}
                  onChange={(e) => setMandate(e.target.value)}
                >
                  {MANDATES.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </Select>
              </Labeled>
            )}

            {localError && <ErrorMsg error={new Error(localError)} />}
            {serverKyc.length > 0 ? (
              <KycList items={serverKyc} sessionId={sessionId} customerId={customerId} />
            ) : (
              <ErrorMsg error={open.error} />
            )}
          </DialogBody>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              disabled={open.isPending}
              onClick={onClose}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={open.isPending || kycBlocked || (!!customerId && customer.isPending)}
            >
              {open.isPending ? "Opening…" : "Open account"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
