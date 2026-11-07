"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold text-text-strong">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

export function errorText(e: unknown): string {
  return e instanceof Error ? e.message : "Something went wrong";
}

export function ErrorMsg({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <p
      role="alert"
      className="rounded-md bg-fin-danger-bg px-3 py-2 text-sm text-fin-danger"
    >
      {errorText(error)}
    </p>
  );
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div role="status" className="py-8 text-sm text-text-muted">
      {label}
    </div>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-border bg-card px-4 py-8 text-center text-sm text-text-muted">
      {children}
    </div>
  );
}

/** Renders loading / error / children for a TanStack query. */
export function QueryState({
  query,
  children,
}: {
  query: { isPending: boolean; isError: boolean; error: unknown };
  children: React.ReactNode;
}) {
  if (query.isPending) return <Loading />;
  if (query.isError) return <ErrorMsg error={query.error} />;
  return <>{children}</>;
}

const STATUS_STYLE: Record<string, string> = {
  active: "bg-fin-success-bg text-fin-success-dark",
  open: "bg-fin-success-bg text-fin-success-dark",
  draft: "bg-fin-pending-bg text-fin-pending",
  archived: "bg-hover text-text-muted",
  closed: "bg-hover text-text-muted",
  inactive: "bg-hover text-text-muted",
};

export function StatusBadge({
  status,
  label,
}: {
  status: string;
  label?: string;
}) {
  return (
    <Badge className={cn("capitalize", STATUS_STYLE[status] ?? "bg-hover text-text-muted")}>
      {label ?? status}
    </Badge>
  );
}

export function Tabs({
  tabs,
  value,
  onChange,
}: {
  tabs: { id: string; label: string }[];
  value: string;
  onChange: (id: string) => void;
}) {
  return (
    <div role="tablist" className="mb-4 flex gap-1 border-b border-border">
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          role="tab"
          aria-selected={value === t.id}
          onClick={() => onChange(t.id)}
          className={cn(
            "-mb-px border-b-2 px-4 py-2 text-sm font-medium",
            value === t.id
              ? "border-bank-primary text-bank-primary"
              : "border-transparent text-text-muted hover:text-text-strong",
          )}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function Table({ children }: { children: React.ReactNode }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-card">
      <table className="w-full text-left text-sm text-text-body">
        {children}
      </table>
    </div>
  );
}
export const Th = ({
  children,
  className,
}: {
  children?: React.ReactNode;
  className?: string;
}) => (
  <th
    className={cn(
      "border-b border-border px-3 py-2 text-xs font-medium uppercase tracking-wide text-text-muted",
      className,
    )}
  >
    {children}
  </th>
);
export const Td = ({
  children,
  className,
}: {
  children?: React.ReactNode;
  className?: string;
}) => (
  <td className={cn("border-b border-border px-3 py-2 align-middle", className)}>
    {children}
  </td>
);

const controlCls =
  "h-9 rounded-md border border-border bg-card px-3 text-sm text-text-body outline-none focus-visible:ring-2 focus-visible:ring-bank-accent disabled:opacity-50";

export function TextInput({
  className,
  ...props
}: React.ComponentProps<"input">) {
  return <input className={cn(controlCls, "w-full", className)} {...props} />;
}

export function Select({
  className,
  ...props
}: React.ComponentProps<"select">) {
  return <select className={cn(controlCls, className)} {...props} />;
}

export function Labeled({
  label,
  error,
  hint,
  children,
}: {
  label: string;
  error?: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block space-y-1.5">
      <span className="text-sm font-medium text-text-strong">{label}</span>
      {children}
      {hint && !error && <span className="block text-xs text-text-muted">{hint}</span>}
      {error && <span className="block text-sm text-fin-danger">{error}</span>}
    </label>
  );
}

/** Two-step inline confirmation (no browser dialogs). */
export function ConfirmButton({
  label,
  confirmLabel = "Confirm",
  message,
  onConfirm,
  pending,
  variant = "outline",
  size = "sm",
}: {
  label: string;
  confirmLabel?: string;
  message: string;
  onConfirm: () => void;
  pending?: boolean;
  variant?: "outline" | "destructive" | "default";
  size?: "sm" | "default";
}) {
  const [asking, setAsking] = useState(false);
  if (!asking)
    return (
      <Button variant={variant} size={size} onClick={() => setAsking(true)}>
        {label}
      </Button>
    );
  return (
    <div
      role="alertdialog"
      aria-label={message}
      className="flex flex-wrap items-center gap-2 rounded-md bg-fin-pending-bg px-3 py-1.5 text-sm text-text-strong"
    >
      <span>{message}</span>
      <Button
        size="sm"
        disabled={pending}
        onClick={() => {
          onConfirm();
          setAsking(false);
        }}
      >
        {pending ? "Working…" : confirmLabel}
      </Button>
      <Button size="sm" variant="outline" onClick={() => setAsking(false)}>
        Cancel
      </Button>
    </div>
  );
}

export function ReadOnlyBanner() {
  return (
    <div
      role="status"
      className="mb-4 rounded-md bg-hover px-4 py-2 text-sm font-medium text-text-muted ring-1 ring-border"
    >
      Read-only: this session is archived. No changes can be made.
    </div>
  );
}

export const formatTemplateLabel = (s: string) =>
  s === "per_group" ? "Per group" : "Single bank";
