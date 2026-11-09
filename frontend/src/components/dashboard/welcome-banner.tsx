"use client";

import { CalendarDays, Eye } from "lucide-react";
import { roleLabel } from "@/lib/lab";
import { useMe } from "@/lib/auth";
import type { SessionMe } from "@/lib/api/types";

function greeting(h = new Date().getHours()) {
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1 text-xs font-medium text-text-body">
      {children}
    </span>
  );
}

/** Soft welcome banner: greeting and context on the left, role chips on the right. */
export function WelcomeBanner({ d }: { d: SessionMe }) {
  const me = useMe();
  const first = me.data?.full_name?.trim().split(/\s+/)[0];
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-bank-sky-light px-5 py-4">
      <div className="min-w-0">
        <h1 className="text-xl font-semibold tracking-tight text-text-strong sm:text-2xl">
          {greeting()}
          {first ? `, ${first}` : ""}
        </h1>
        <p className="mt-0.5 text-sm text-text-muted">
          {[d.bank_name, d.class_name, d.kind === "exam" ? "Exam" : "Practice"]
            .filter(Boolean)
            .join(" · ")}
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {d.role && (
          <span className="inline-flex rounded-full bg-bank-primary px-3 py-1 text-xs font-semibold text-white">
            {roleLabel(d.role)}
          </span>
        )}
        <Chip>
          <Eye className="size-3.5 text-bank-primary" aria-hidden />
          Visibility: {d.visibility === "own" ? "Own work only" : "Whole bank"}
        </Chip>
        {d.business_date && (
          <Chip>
            <CalendarDays className="size-3.5 text-bank-primary" aria-hidden />
            Business date {d.business_date}
          </Chip>
        )}
      </div>
    </div>
  );
}
