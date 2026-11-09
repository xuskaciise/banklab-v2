"use client";

import { useMemo, useRef, useState } from "react";
import { Lock, Search } from "lucide-react";
import type { TillAvailability } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { Input, Select } from "@/components/ui/input";
import { Pagination } from "@/components/shared/pagination";

const PAGE_SIZE = 25;
const COLS = "sm:grid-cols-[6rem_minmax(0,1fr)_minmax(0,1fr)_10rem]";

function Status({ t }: { t: TillAvailability }) {
  return t.available ? (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-fin-success-bg px-2 py-0.5 text-xs font-medium text-fin-success">
      <span className="size-1.5 rounded-full bg-fin-success" aria-hidden />
      Free
    </span>
  ) : (
    <span className="inline-flex max-w-full items-center gap-1.5 rounded-full bg-fin-pending-bg px-2 py-0.5 text-xs font-medium text-fin-pending">
      <Lock className="size-3 shrink-0" aria-hidden />
      <span className="truncate">
        in use{t.in_use_by ? ` · ${t.in_use_by}` : ""}
      </span>
    </span>
  );
}

/** Searchable, filterable, paged till list with radio semantics. */
export function TillSelector({
  tills,
  value,
  onChange,
}: {
  tills: TillAvailability[];
  value: string;
  onChange: (id: string) => void;
}) {
  const [q, setQ] = useState("");
  const [branch, setBranch] = useState("");
  const [location, setLocation] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  const branches = useMemo(() => {
    const m = new Map<string, string>();
    for (const t of tills) m.set(t.branch_id, `${t.branch_name} (${t.branch_code})`);
    return Array.from(m.entries()).sort((a, b) => a[1].localeCompare(b[1]));
  }, [tills]);
  const locations = useMemo(
    () =>
      Array.from(new Set(tills.map((t) => t.branch_address).filter(Boolean))).sort(),
    [tills],
  );
  const filtered = useMemo(() => {
    const term = q.trim().toLowerCase();
    return tills.filter(
      (t) =>
        (!branch || t.branch_id === branch) &&
        (!location || t.branch_address === location) &&
        (!status || (status === "free") === t.available) &&
        (!term ||
          `${t.code} ${t.branch_code} ${t.branch_name} ${t.branch_address}`
            .toLowerCase()
            .includes(term)),
    );
  }, [tills, q, branch, location, status]);
  const rows = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const reset = <T,>(set: (v: T) => void) => (v: T) => {
    set(v);
    setPage(1);
  };

  function onKey(e: React.KeyboardEvent, i: number) {
    const step =
      e.key === "ArrowDown" || e.key === "ArrowRight"
        ? 1
        : e.key === "ArrowUp" || e.key === "ArrowLeft"
          ? -1
          : 0;
    if (!step) return;
    e.preventDefault();
    for (let j = i + step; j >= 0 && j < rows.length; j += step) {
      if (rows[j].available) {
        onChange(rows[j].id);
        refs.current[rows[j].id]?.focus();
        return;
      }
    }
  }
  const tabbable = rows.find((t) => t.id === value && t.available)
    ? value
    : rows.find((t) => t.available)?.id;

  return (
    <div className="space-y-3">
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <div className="relative sm:col-span-2 lg:col-span-4">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-text-muted" />
          <Input
            aria-label="Search tills"
            placeholder="Search till code, branch or address…"
            value={q}
            onChange={(e) => reset(setQ)(e.target.value)}
            className="h-10 pl-9"
          />
        </div>
        <Select
          aria-label="Filter by branch"
          value={branch}
          onChange={(e) => reset(setBranch)(e.target.value)}
          className="h-10 w-full lg:col-span-2"
        >
          <option value="">All branches</option>
          {branches.map(([id, label]) => (
            <option key={id} value={id}>
              {label}
            </option>
          ))}
        </Select>
        <Select
          aria-label="Filter by location"
          value={location}
          onChange={(e) => reset(setLocation)(e.target.value)}
          className="h-10 w-full"
        >
          <option value="">All locations</option>
          {locations.map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </Select>
        <Select
          aria-label="Filter by status"
          value={status}
          onChange={(e) => reset(setStatus)(e.target.value)}
          className="h-10 w-full"
        >
          <option value="">All statuses</option>
          <option value="free">Free</option>
          <option value="occupied">Occupied</option>
        </Select>
      </div>
      <p className="text-xs text-text-muted" aria-live="polite">
        Showing {filtered.length} of {tills.length} tills
      </p>

      {filtered.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border bg-surface px-4 py-8 text-center text-sm text-text-muted">
          No tills match these filters.
        </p>
      ) : (
        <div className="overflow-hidden rounded-lg border border-border">
          <div
            className={cn(
              "hidden gap-3 border-b border-border bg-surface px-3 py-2 text-xs font-medium tracking-wide text-text-muted uppercase sm:grid",
              COLS,
            )}
          >
            <span>Till</span>
            <span>Branch</span>
            <span>Location</span>
            <span>Status</span>
          </div>
          <div role="radiogroup" aria-label="Till" className="max-h-[28rem] divide-y divide-border overflow-y-auto">
            {rows.map((t, i) => {
              const on = t.id === value;
              return (
                <button
                  key={t.id}
                  ref={(el) => {
                    refs.current[t.id] = el;
                  }}
                  type="button"
                  role="radio"
                  aria-checked={on}
                  disabled={!t.available}
                  tabIndex={t.id === tabbable ? 0 : -1}
                  onClick={() => onChange(t.id)}
                  onKeyDown={(e) => onKey(e, i)}
                  className={cn(
                    "grid w-full items-center gap-x-3 gap-y-1 px-3 py-2.5 text-left text-sm transition-colors outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-bank-accent disabled:cursor-not-allowed",
                    COLS,
                    on
                      ? "bg-bank-sky-light"
                      : t.available
                        ? "bg-card hover:bg-hover"
                        : "bg-surface",
                  )}
                >
                  <span
                    className={cn(
                      "font-mono font-semibold",
                      t.available ? "text-text-strong" : "text-text-muted",
                    )}
                  >
                    {t.code}
                  </span>
                  <span className="min-w-0 truncate text-text-body">
                    {t.branch_name}{" "}
                    <span className="text-xs text-text-muted">{t.branch_code}</span>
                  </span>
                  <span className="min-w-0 truncate text-text-muted">
                    {t.branch_address || "No address"}
                  </span>
                  <span className="min-w-0">
                    <Status t={t} />
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}
      {filtered.length > PAGE_SIZE && (
        <Pagination
          page={page}
          pageSize={PAGE_SIZE}
          total={filtered.length}
          onPageChange={setPage}
        />
      )}
    </div>
  );
}
