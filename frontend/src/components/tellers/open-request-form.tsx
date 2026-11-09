"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Check, Landmark, Loader2, Lock, Send } from "lucide-react";
import { useTellerAction, useTillAvailability } from "@/lib/tellers";
import { FormActions, FormGrid, FormSection } from "@/components/shared/form-layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorMsg, Loading } from "@/components/lab/common";
import { FieldLabel } from "@/components/transactions/field-label";
import { cn } from "@/lib/utils";
import { CURRENCIES } from "./session-bits";

const FOCUS =
  "outline-none focus-visible:ring-2 focus-visible:ring-bank-accent focus-visible:ring-offset-2";

const STEPS = [
  "Pick a free till and, if you need cash, the opening float.",
  "Your manager approves the request (and the vault releases the float).",
  "Serve customers. At the end of the day count your cash and close the till.",
];

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

  const free = tills.data.filter((t) => t.available).length;

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
      className="grid max-w-6xl gap-6 lg:grid-cols-[minmax(0,1fr)_320px] lg:items-start"
    >
      <div className="space-y-6">
        <FormSection
          title="Choose your till"
          description={`${free} of ${tills.data.length} tills are free today.`}
        >
          <div
            role="radiogroup"
            aria-label="Till"
            className="grid gap-3 sm:grid-cols-3 lg:grid-cols-4"
          >
            {tills.data.map((t) => {
              const on = t.id === tillId;
              return (
                <button
                  key={t.id}
                  type="button"
                  role="radio"
                  aria-checked={on}
                  disabled={!t.available}
                  onClick={() => setTillId(t.id)}
                  className={cn(
                    "relative rounded-lg border p-3 text-left transition-colors disabled:cursor-not-allowed",
                    FOCUS,
                    on
                      ? "border-bank-primary bg-bank-sky-light"
                      : t.available
                        ? "border-border bg-card hover:bg-hover"
                        : "border-dashed border-border bg-surface",
                  )}
                >
                  <span className="flex items-center justify-between gap-2">
                    <span
                      className={cn(
                        "font-mono text-sm font-semibold",
                        t.available ? "text-text-strong" : "text-text-muted",
                      )}
                    >
                      {t.code}
                    </span>
                    {on ? (
                      <Check className="size-4 text-bank-primary" aria-hidden />
                    ) : (
                      !t.available && <Lock className="size-3.5 text-text-muted" aria-hidden />
                    )}
                  </span>
                  <span className="mt-1 block text-xs text-text-muted">
                    Branch {t.branch_code}
                  </span>
                  <span
                    className={cn(
                      "mt-2 block truncate text-xs font-medium",
                      t.available ? "text-fin-success-dark" : "text-text-muted",
                    )}
                  >
                    {t.available ? "Free" : `In use${t.in_use_by ? ` · ${t.in_use_by}` : ""}`}
                  </span>
                </button>
              );
            })}
          </div>
        </FormSection>

        <FormSection
          title="Opening float"
          description="Cash you want from the vault to start the day. Leave empty to start with no cash."
        >
          <FormGrid>
            {CURRENCIES.map((c) => (
              <div key={c} className="space-y-1.5">
                <FieldLabel htmlFor={`float-${c}`} optional>
                  {c}
                </FieldLabel>
                <div className="flex items-stretch overflow-hidden rounded-lg border border-border bg-card focus-within:ring-2 focus-within:ring-bank-accent">
                  <span className="flex items-center border-r border-border bg-surface px-3 text-sm font-semibold text-text-body">
                    {c}
                  </span>
                  <Input
                    id={`float-${c}`}
                    inputMode="decimal"
                    placeholder="0.00"
                    value={floats[c] ?? ""}
                    onChange={(e) => setFloats({ ...floats, [c]: e.target.value })}
                    className="rounded-none border-0 text-right text-base tabular-nums shadow-none focus-visible:ring-0"
                  />
                </div>
              </div>
            ))}
          </FormGrid>
        </FormSection>

        {err && <ErrorMsg error={new Error(err)} />}
        <FormActions>
          <Button type="submit" disabled={act.isPending || !tillId}>
            {act.isPending ? <Loader2 className="animate-spin" /> : <Send />}
            {act.isPending ? "Sending…" : "Request to open"}
          </Button>
        </FormActions>
      </div>

      <aside className="rounded-xl border border-border bg-card p-5 shadow-xs lg:sticky lg:top-4">
        <h3 className="text-sm font-semibold text-text-strong">How opening works</h3>
        <ol className="mt-3 space-y-3">
          {STEPS.map((s, i) => (
            <li key={s} className="flex gap-3 text-sm text-text-body">
              <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-bank-sky-light text-xs font-semibold text-bank-primary">
                {i + 1}
              </span>
              {s}
            </li>
          ))}
        </ol>
      </aside>
    </form>
  );
}
