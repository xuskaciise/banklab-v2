"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input, Select as SelectBase } from "@/components/ui/input";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { EmptyState } from "@/components/shared/empty-state";
import { LoadingSkeleton } from "@/components/shared/loading-skeleton";
import { cn } from "@/lib/utils";

export { PageHeader } from "@/components/shared/page-header";
export { StatusBadge } from "@/components/shared/status-badge";

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

export function Loading({ label = "Loading" }: { label?: string }) {
  return <LoadingSkeleton label={label} />;
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <EmptyState title="Nothing here yet" description={children} />;
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

export function Tabs({
  tabs,
  value,
  onChange,
}: {
  tabs: { id: string; label: string; count?: number }[];
  value: string;
  onChange: (id: string) => void;
}) {
  return (
    <div className="mb-6 border-b border-border">
      <div
        role="tablist"
        className="-mb-px flex gap-1 overflow-x-auto overflow-y-hidden [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        {tabs.map((t) => {
          const active = value === t.id;
          return (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => onChange(t.id)}
              className={cn(
                "flex shrink-0 items-center gap-2 border-b-2 px-3.5 py-2.5 text-sm font-medium whitespace-nowrap transition-colors",
                active
                  ? "border-bank-primary text-bank-primary"
                  : "border-transparent text-text-muted hover:border-border hover:text-text-strong",
              )}
            >
              {t.label}
              {t.count !== undefined && (
                <span
                  className={cn(
                    "rounded-full px-1.5 text-xs tabular-nums",
                    active
                      ? "bg-bank-sky-light text-bank-primary"
                      : "bg-hover text-text-muted",
                  )}
                >
                  {t.count}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** Simple bordered table for small static lists; scrolls inside its box. */
export function Table({ children }: { children: React.ReactNode }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-card shadow-xs">
      <table className="w-full min-w-max text-left text-sm text-text-body">
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
      "border-b border-border bg-surface px-4 py-2.5 text-xs font-medium tracking-wide whitespace-nowrap text-text-muted uppercase",
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
  <td className={cn("border-b border-border px-4 py-3 align-middle", className)}>
    {children}
  </td>
);

export function TextInput({
  className,
  ...props
}: React.ComponentProps<"input">) {
  return <Input className={className} {...props} />;
}

export function Select({
  className,
  ...props
}: React.ComponentProps<"select">) {
  return <SelectBase className={cn("w-auto", className)} {...props} />;
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
      {hint && !error && (
        <span className="block text-xs text-text-muted">{hint}</span>
      )}
      {error && <span className="block text-sm text-fin-danger">{error}</span>}
    </label>
  );
}

/** Button that asks for confirmation in a dialog before running the action. */
export function ConfirmButton({
  label,
  confirmLabel = "Confirm",
  title,
  message,
  onConfirm,
  pending,
  variant = "outline",
  size = "sm",
}: {
  label: string;
  confirmLabel?: string;
  title?: string;
  message: string;
  onConfirm: () => void;
  pending?: boolean;
  variant?: "outline" | "destructive" | "default";
  size?: "sm" | "default";
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant={variant} size={size} onClick={() => setOpen(true)}>
        {label}
      </Button>
      <ConfirmDialog
        open={open}
        onOpenChange={setOpen}
        title={title ?? label}
        description={message}
        confirmLabel={confirmLabel === "Confirm" ? label : confirmLabel}
        destructive={variant === "destructive"}
        pending={pending}
        onConfirm={() => {
          onConfirm();
          setOpen(false);
        }}
      />
    </>
  );
}

export function ReadOnlyBanner() {
  return (
    <div
      role="status"
      className="mb-4 rounded-lg border border-fin-pending/30 bg-fin-pending-bg px-4 py-2.5 text-sm font-medium text-fin-pending"
    >
      Read-only: this session is archived. No changes can be made.
    </div>
  );
}

export const formatTemplateLabel = (s: string) =>
  s === "per_group" ? "Per group" : "Single bank";
