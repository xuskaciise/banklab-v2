"use client";

import { useRef } from "react";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/shared/page-header";

/** Centered form page: heading + subtitle, content, optional sticky aside. */
export function FormPage({
  title,
  subtitle,
  aside,
  children,
}: {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  aside?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "mx-auto w-full space-y-6",
        aside ? "max-w-6xl" : "max-w-3xl",
      )}
    >
      <PageHeader title={title} subtitle={subtitle} className="mb-0" />
      {aside ? (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,13fr)_minmax(0,7fr)]">
          <div className="space-y-6">{children}</div>
          <aside>{aside}</aside>
        </div>
      ) : (
        <div className="space-y-6">{children}</div>
      )}
    </div>
  );
}

/** Titled card grouping related fields. */
export function FormSection({
  title,
  description,
  children,
  className,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && (
          <p className="text-sm font-normal text-text-muted">{description}</p>
        )}
      </CardHeader>
      <CardContent className={cn("space-y-4", className)}>{children}</CardContent>
    </Card>
  );
}

/** 1 column on mobile, 2 (or 3) from sm. */
export function FormGrid({
  cols = 2,
  className,
  children,
}: {
  cols?: 2 | 3;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "grid gap-4",
        cols === 2 ? "sm:grid-cols-2" : "sm:grid-cols-3",
        className,
      )}
    >
      {children}
    </div>
  );
}

/** Bottom action bar: secondary on the left of primary; stacked on mobile. */
export function FormActions({
  hint,
  children,
  className,
}: {
  hint?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-end",
        className,
      )}
    >
      {hint && <p className="text-xs text-text-muted sm:mr-auto">{hint}</p>}
      {children}
    </div>
  );
}

export type Option<T extends string> = {
  value: T;
  label: string;
  hint?: string;
  icon?: React.ComponentType<{ className?: string }>;
};

/** Radio-group of selectable cards; arrow keys move the selection. */
export function OptionCards<T extends string>({
  label,
  options,
  value,
  onChange,
  disabled,
  columns = 3,
}: {
  label: string;
  options: Option<T>[];
  value: T;
  onChange: (v: T) => void;
  disabled?: boolean;
  columns?: 2 | 3;
}) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  function onKey(e: React.KeyboardEvent, i: number) {
    const step =
      e.key === "ArrowRight" || e.key === "ArrowDown"
        ? 1
        : e.key === "ArrowLeft" || e.key === "ArrowUp"
          ? -1
          : 0;
    if (!step || disabled) return;
    e.preventDefault();
    const next = options[(i + step + options.length) % options.length].value;
    onChange(next);
    refs.current[next]?.focus();
  }

  return (
    <div
      role="radiogroup"
      aria-label={label}
      className={cn(
        "grid gap-3",
        columns === 3 ? "sm:grid-cols-3" : "sm:grid-cols-2",
      )}
    >
      {options.map((o, i) => {
        const active = o.value === value;
        const Icon = o.icon;
        return (
          <button
            key={o.value}
            ref={(el) => {
              refs.current[o.value] = el;
            }}
            type="button"
            role="radio"
            aria-checked={active}
            disabled={disabled}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(o.value)}
            onKeyDown={(e) => onKey(e, i)}
            className={cn(
              "flex items-start gap-3 rounded-xl border p-4 text-left transition-colors outline-none",
              "focus-visible:ring-2 focus-visible:ring-bank-accent focus-visible:ring-offset-2",
              "disabled:cursor-not-allowed disabled:opacity-60",
              active
                ? "border-bank-primary bg-bank-sky-light"
                : "border-border bg-card hover:border-bank-accent hover:bg-surface",
            )}
          >
            {Icon && (
              <span
                className={cn(
                  "flex size-9 shrink-0 items-center justify-center rounded-lg",
                  active
                    ? "bg-bank-primary text-white"
                    : "bg-surface text-bank-primary",
                )}
              >
                <Icon className="size-5" aria-hidden />
              </span>
            )}
            <span className="min-w-0">
              <span className="block text-sm font-semibold text-text-strong">
                {o.label}
              </span>
              {o.hint && (
                <span className="block text-xs text-text-muted">{o.hint}</span>
              )}
            </span>
          </button>
        );
      })}
    </div>
  );
}

/** Summary card: label/value rows, or an empty-state message. */
export function SummaryCard({
  title,
  rows,
  empty,
  children,
}: {
  title: string;
  rows?: { label: string; value: React.ReactNode }[];
  empty?: string;
  children?: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {empty ? (
          <p className="rounded-lg bg-surface p-4 text-center text-sm text-text-muted">
            {empty}
          </p>
        ) : (
          <dl className="divide-y divide-border">
            {rows?.map((r) => (
              <div
                key={r.label}
                className="flex items-start justify-between gap-3 py-2 text-sm"
              >
                <dt className="text-text-muted">{r.label}</dt>
                <dd className="text-right font-medium text-text-strong">
                  {r.value}
                </dd>
              </div>
            ))}
            {children}
          </dl>
        )}
      </CardContent>
    </Card>
  );
}
