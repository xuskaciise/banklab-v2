"use client";

import { useState } from "react";
import { toast } from "sonner";
import { formatMoney } from "@/lib/banking";
import { useDenominations, useTellerAction } from "@/lib/tellers";
import type { TellerSession } from "@/lib/api/types";
import {
  FormActions,
  FormSection,
} from "@/components/shared/form-layout";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ErrorMsg, Loading } from "@/components/lab/common";
import { nonZeroCurrencies, useCurrencies } from "@/lib/platform";
import { Difference } from "./session-bits";

/** Denomination count. Live totals are a display aid; the server recomputes. */
export function CloseCountForm({
  sid,
  s,
  onDone,
}: {
  sid: string;
  s: TellerSession;
  onDone: () => void;
}) {
  const currencies = useCurrencies(nonZeroCurrencies(s.balances));
  const denoms = useDenominations();
  const act = useTellerAction(sid);
  const [qty, setQty] = useState<Record<number, string>>({});
  const [err, setErr] = useState<string | null>(null);

  if (denoms.isPending) return <Loading label="Loading denominations" />;
  if (denoms.isError) return <ErrorMsg error={denoms.error} />;

  const q = (id: number) => Math.max(0, Math.floor(Number(qty[id] || 0)) || 0);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    for (const d of denoms.data ?? [])
      if (qty[d.id] && !/^\d+$/.test(qty[d.id]))
        return setErr("Quantities must be whole numbers");
    setErr(null);
    act.mutate(
      {
        kind: "close-count",
        id: s.id,
        body: {
          counts: currencies.map((c) => ({
            currency: c,
            lines: (denoms.data ?? [])
              .filter((d) => d.currency === c && q(d.id) > 0)
              .map((d) => ({ denomination_id: d.id, quantity: q(d.id) })),
          })),
        },
      },
      {
        onSuccess: () => {
          toast.success("Count submitted to your manager");
          onDone();
        },
        onError: (e) => setErr(e.message),
      },
    );
  }

  return (
    <form onSubmit={submit} className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-2">
        {currencies.map((c) => {
          const rows = (denoms.data ?? []).filter((d) => d.currency === c);
          const counted = rows.reduce(
            (a, d) => a + Number(d.value) * q(d.id),
            0,
          );
          const system =
            s.balances.find((b) => b.currency === c)?.balance ?? "0";
          return (
            <FormSection key={c} title={`${c} cash count`} className="space-y-2">
              {rows.map((d) => (
                <div key={d.id} className="flex items-center gap-3 text-sm">
                  <span className="w-24 text-text-muted tabular-nums">
                    {d.value} <span className="text-xs">{d.kind}</span>
                  </span>
                  <span aria-hidden="true">×</span>
                  <Input
                    aria-label={`${c} ${d.value} quantity`}
                    inputMode="numeric"
                    placeholder="0"
                    className="h-8 w-24"
                    value={qty[d.id] ?? ""}
                    onChange={(e) => setQty({ ...qty, [d.id]: e.target.value })}
                  />
                  <span className="ml-auto text-text-muted tabular-nums">
                    {formatMoney(Number(d.value) * q(d.id), c)}
                  </span>
                </div>
              ))}
              <dl className="space-y-1 border-t border-border pt-2 text-sm">
                <div className="flex justify-between">
                  <dt className="text-text-muted">Counted</dt>
                  <dd className="font-medium tabular-nums">
                    {formatMoney(counted, c)}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-text-muted">System</dt>
                  <dd className="tabular-nums">{formatMoney(system, c)}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-text-muted">Difference</dt>
                  <dd>
                    <Difference value={counted - Number(system)} currency={c} />
                  </dd>
                </div>
              </dl>
            </FormSection>
          );
        })}
      </div>
      {err && <ErrorMsg error={new Error(err)} />}
      <FormActions>
        <Button
          type="button"
          variant="outline"
          onClick={onDone}
          disabled={act.isPending}
        >
          Cancel
        </Button>
        <Button type="submit" disabled={act.isPending}>
          {act.isPending && <Loader2 className="animate-spin" />}
          {act.isPending ? "Submitting…" : "Submit count"}
        </Button>
      </FormActions>
    </form>
  );
}
