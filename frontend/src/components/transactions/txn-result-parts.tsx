"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { cn } from "@/lib/utils";

const TYPE_TONE: Record<string, string> = {
  cash_deposit: "bg-fin-success-bg text-fin-success-dark",
  cash_withdrawal: "bg-fin-pending-bg text-fin-pending",
  transfer: "bg-bank-sky-light text-bank-primary",
};

export function TypeBadge({ type, label }: { type: string; label: string }) {
  return (
    <span
      className={cn(
        "inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold",
        TYPE_TONE[type] ?? "bg-hover text-text-body",
      )}
    >
      {label}
    </span>
  );
}

export function DetailRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4 py-2.5 text-sm">
      <dt className="shrink-0 text-text-muted">{label}</dt>
      <dd className="min-w-0 text-right font-medium break-words text-text-strong">
        {children}
      </dd>
    </div>
  );
}

/** Reference number with a copy button and a 1.5 s "Copied" confirmation. */
export function CopyRef({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable: ignore */
    }
  }
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="font-mono">{value}</span>
      <button
        type="button"
        onClick={copy}
        aria-label="Copy reference"
        className="inline-flex size-6 items-center justify-center rounded-md text-text-muted transition-colors outline-none hover:bg-hover hover:text-text-strong focus-visible:ring-2 focus-visible:ring-bank-accent"
      >
        {copied ? (
          <Check className="size-3.5 text-fin-success" aria-hidden />
        ) : (
          <Copy className="size-3.5" aria-hidden />
        )}
      </button>
      <span aria-live="polite" className="text-xs font-normal text-fin-success">
        {copied ? "Copied" : ""}
      </span>
    </span>
  );
}
