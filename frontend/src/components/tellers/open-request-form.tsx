"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Landmark } from "lucide-react";
import { useTellerAction, useTillAvailability } from "@/lib/tellers";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorMsg, Labeled, Loading } from "@/components/lab/common";
import { CURRENCIES } from "./session-bits";

export function OpenRequestForm({ sid }: { sid: string }) {
  const tills = useTillAvailability(sid);
  const act = useTellerAction(sid);
  const [tillId, setTillId] = useState("");
  const [floats, setFloats] = useState<Record<string, string>>({});
  const [err, setErr] = useState<string | null>(null);

  if (tills.isPending) return <Loading label="Loading tills" />;
  if (tills.isError) return <ErrorMsg error={tills.error} />;
  if (!tills.data.length)
    return (
      <EmptyState
        icon={Landmark}
        title="No tills"
        description="Your manager has not created a till for this bank yet."
      />
    );

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!tillId) return setErr("Choose a till");
    const lines: { currency: string; amount: number }[] = [];
    for (const c of CURRENCIES) {
      const raw = (floats[c] ?? "").trim();
      if (!raw) continue;
      const n = Number(raw);
      if (!Number.isFinite(n) || n < 0)
        return setErr(`Enter a valid ${c} opening float`);
      if (n > 0) lines.push({ currency: c, amount: n });
    }
    setErr(null);
    act.mutate(
      { kind: "open-request", body: { till_id: tillId, floats: lines } },
      {
        onSuccess: () => toast.success("Opening request sent to your manager"),
        onError: (e) => setErr(e.message),
      },
    );
  }

  return (
    <form
      onSubmit={submit}
      className="max-w-xl space-y-4 rounded-xl border border-border bg-card p-5 shadow-xs"
    >
      <h2 className="text-sm font-semibold text-text-strong">Open my till</h2>
      <Labeled label="Till">
        <Select value={tillId} onChange={(e) => setTillId(e.target.value)}>
          <option value="">Select a till…</option>
          {tills.data.map((t) => (
            <option key={t.id} value={t.id} disabled={!t.available}>
              {t.code} · {t.branch_code}
              {!t.available &&
                ` (in use${t.in_use_by ? ` by ${t.in_use_by}` : ""})`}
            </option>
          ))}
        </Select>
      </Labeled>
      <div className="grid gap-4 sm:grid-cols-2">
        {CURRENCIES.map((c) => (
          <Labeled key={c} label={`Opening float ${c} (optional)`}>
            <Input
              inputMode="decimal"
              placeholder="0.00"
              value={floats[c] ?? ""}
              onChange={(e) => setFloats({ ...floats, [c]: e.target.value })}
            />
          </Labeled>
        ))}
      </div>
      <p className="text-xs text-text-muted">
        An opening float is requested from the vault and needs approval before
        the till opens.
      </p>
      {err && <ErrorMsg error={new Error(err)} />}
      <Button type="submit" disabled={act.isPending}>
        {act.isPending ? "Sending…" : "Request open"}
      </Button>
    </form>
  );
}
