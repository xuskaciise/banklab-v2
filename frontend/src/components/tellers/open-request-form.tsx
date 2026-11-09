"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Landmark } from "lucide-react";
import { useTellerAction, useTillAvailability } from "@/lib/tellers";
import { EmptyState } from "@/components/shared/empty-state";
import { FormSection } from "@/components/shared/form-layout";
import { ErrorMsg, Loading } from "@/components/lab/common";
import { OpenTillForm } from "./open-till-form";
import { CURRENCIES } from "./session-bits";
import { TillSelector } from "./till-selector";

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
      noValidate
      className="grid gap-6 lg:grid-cols-[minmax(0,13fr)_minmax(0,7fr)] lg:items-start"
    >
      <FormSection
        title="Choose your till"
        description="Pick a free till. Occupied tills are shown but cannot be selected."
      >
        <TillSelector tills={tills.data} value={tillId} onChange={setTillId} />
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
