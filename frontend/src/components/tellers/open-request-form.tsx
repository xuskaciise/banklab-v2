"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Landmark } from "lucide-react";
import { useTellerAction, useTillAvailability } from "@/lib/tellers";
import { EmptyState } from "@/components/shared/empty-state";
import { FormSection } from "@/components/shared/form-layout";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorMsg } from "@/components/lab/common";
import { stripAmount } from "./amount-input";
import { OpenTillForm, TillSummary } from "./open-till-form";
import { CURRENCIES } from "./session-bits";
import { TillSelector } from "./till-selector";

export function OpenRequestForm({ sid }: { sid: string }) {
  const tills = useTillAvailability(sid);
  const act = useTellerAction(sid);
  const [tillId, setTillId] = useState("");
  const [floats, setFloats] = useState<Record<string, string>>({});
  const [err, setErr] = useState<string | null>(null);

  if (tills.isPending)
    return (
      <div className="mx-auto w-full max-w-3xl space-y-4" aria-busy="true">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-44 w-full rounded-xl" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    );
  if (tills.isError) return <ErrorMsg error={tills.error} />;
  if (!tills.data.length)
    return (
      <EmptyState
        icon={Landmark}
        title="No tills"
        description="Your instructor has not created a till for this bank yet (Branches tab)."
      />
    );

  const selected = tills.data.find((t) => t.id === tillId);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (act.isPending) return;
    if (!tillId) return setErr("Choose a till");
    const lines: { currency: string; amount: number }[] = [];
    for (const c of CURRENCIES) {
      const raw = stripAmount(floats[c] ?? "").trim();
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
        onSuccess: () =>
          toast.success("Request sent — waiting for manager approval"),
        onError: (e) => setErr(e.message),
      },
    );
  }

  return (
    <form
      onSubmit={submit}
      noValidate
      className="grid w-full gap-6 lg:grid-flow-dense lg:grid-cols-[minmax(0,1fr)_360px] lg:items-start"
    >
      <div>
        <h2 className="text-lg font-semibold tracking-tight text-text-strong">
          Open Till
        </h2>
        <p className="text-sm text-text-muted">
          Choose a free till and request an opening float from the vault.
        </p>
      </div>
      <FormSection title="Choose your till">
        <TillSelector tills={tills.data} value={tillId} onChange={setTillId} />
        <TillSummary till={selected} />
      </FormSection>
      <OpenTillForm
        till={selected}
        floats={floats}
        onFloats={setFloats}
        err={err}
        pending={act.isPending}
      />
    </form>
  );
}
