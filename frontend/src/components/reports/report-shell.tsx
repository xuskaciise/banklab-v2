"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { useSessionMe } from "@/lib/lab";
import { buttonVariants } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { EmptyState } from "@/components/shared/empty-state";
import { Labeled, PageHeader, QueryState } from "@/components/lab/common";

/** Page frame for a report screen: header, back link and permission gate. */
export function ReportShell({
  sid,
  title,
  subtitle,
  anyOf,
  back,
  children,
}: {
  sid: string;
  title: string;
  subtitle?: string;
  /** Permission codes; the user needs at least one. */
  anyOf: string[];
  back?: { href: string; label: string };
  children: React.ReactNode;
}) {
  const me = useSessionMe(sid);
  const allowed = !!me.data?.permissions.some((p) => anyOf.includes(p.code));
  return (
    <div className="space-y-2">
      <PageHeader
        title={title}
        subtitle={subtitle}
        actions={
          <Link
            href={back?.href ?? `/s/${sid}/reports`}
            className={buttonVariants({ variant: "outline" })}
          >
            <ArrowLeft /> {back?.label ?? "Reports"}
          </Link>
        }
      />
      <QueryState query={me}>
        {allowed ? (
          children
        ) : (
          <EmptyState title="No access" description="Your role cannot view this report." />
        )}
      </QueryState>
    </div>
  );
}

export function DateField({
  label,
  value,
  onChange,
  optional,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  optional?: boolean;
}) {
  return (
    <Labeled label={label} optional={optional}>
      <Input type="date" value={value} onChange={(e) => onChange(e.target.value)} className="w-44" />
    </Labeled>
  );
}

export function CurrencyField({
  value,
  onChange,
  allowAll,
}: {
  value: string;
  onChange: (v: string) => void;
  allowAll?: boolean;
}) {
  return (
    <Labeled label="Currency">
      <Select value={value} onChange={(e) => onChange(e.target.value)} className="w-36">
        {allowAll && <option value="">All</option>}
        <option value="USD">USD</option>
        <option value="SOS">SOS</option>
      </Select>
    </Labeled>
  );
}

/** Rejects an inverted date range; returns a message or undefined. */
export function rangeError(from: string, to: string) {
  return from && to && from > to ? "The start date is after the end date." : undefined;
}
