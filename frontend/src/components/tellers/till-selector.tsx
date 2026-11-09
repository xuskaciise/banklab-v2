"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { Check, ChevronsUpDown, Lock, Search } from "lucide-react";
import type { TillAvailability } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { FieldLabel } from "@/components/transactions/field-label";

const MAX_SHOWN = 50;

function Status({ t }: { t: TillAvailability }) {
  return t.available ? (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-fin-success-bg px-2 py-0.5 text-xs font-medium text-fin-success">
      <span className="size-1.5 rounded-full bg-fin-success" aria-hidden />
      Free
    </span>
  ) : (
    <span className="inline-flex max-w-40 items-center gap-1.5 rounded-full bg-fin-pending-bg px-2 py-0.5 text-xs font-medium text-fin-pending">
      <Lock className="size-3 shrink-0" aria-hidden />
      <span className="truncate">
        In use{t.in_use_by ? ` · ${t.in_use_by}` : ""}
      </span>
    </span>
  );
}

const describe = (t: TillAvailability) =>
  `${t.code} · ${t.branch_name} ${t.branch_code} · ${t.branch_address || "No address"}`;

/** Searchable till dropdown (ARIA combobox + listbox). */
export function TillSelector({
  tills,
  value,
  onChange,
}: {
  tills: TillAvailability[];
  value: string;
  onChange: (id: string) => void;
}) {
  const uid = useId();
  const listId = `${uid}-list`;
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [freeOnly, setFreeOnly] = useState(true);
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const search = useRef<HTMLInputElement>(null);
  const selected = tills.find((t) => t.id === value);

  const matches = useMemo(() => {
    const term = q.trim().toLowerCase();
    return tills.filter(
      (t) =>
        (!freeOnly || t.available) &&
        (!term ||
          `${t.code} ${t.branch_code} ${t.branch_name} ${t.branch_address}`
            .toLowerCase()
            .includes(term)),
    );
  }, [tills, q, freeOnly]);
  const shown = matches.slice(0, MAX_SHOWN);

  useEffect(() => {
    if (!open) return;
    search.current?.focus();
    const away = (e: MouseEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, [open]);

  function show() {
    setQ("");
    setActive(0);
    setOpen(true);
  }
  function close() {
    setOpen(false);
    trigger.current?.focus();
  }
  function pick(t: TillAvailability) {
    if (!t.available) return;
    onChange(t.id);
    close();
  }
  function move(step: 1 | -1) {
    for (let j = active + step; j >= 0 && j < shown.length; j += step) {
      if (shown[j].available) {
        setActive(j);
        document.getElementById(`${uid}-o${j}`)?.scrollIntoView({ block: "nearest" });
        return;
      }
    }
  }
  function onSearchKey(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      move(1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      move(-1);
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (shown[active]) pick(shown[active]);
    } else if (e.key === "Escape") {
      e.preventDefault();
      close();
    } else if (e.key === "Tab") setOpen(false);
  }

  return (
    <div ref={root} className="relative space-y-1.5">
      <FieldLabel htmlFor={`${uid}-trigger`} required>
        Till
      </FieldLabel>
      <button
        ref={trigger}
        id={`${uid}-trigger`}
        type="button"
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => (open ? setOpen(false) : show())}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown" && !open) {
            e.preventDefault();
            show();
          }
        }}
        className="flex h-11 w-full items-center justify-between gap-2 rounded-lg border border-border bg-card px-3.5 text-left text-sm transition-colors outline-none hover:border-text-muted focus-visible:border-bank-accent focus-visible:ring-2 focus-visible:ring-bank-accent/40"
      >
        <span
          className={cn("truncate", selected ? "text-text-strong" : "text-text-muted")}
        >
          {selected ? describe(selected) : "Search and select a till…"}
        </span>
        <ChevronsUpDown className="size-4 shrink-0 text-text-muted" aria-hidden />
      </button>

      {open && (
        <div className="absolute z-30 mt-1 w-full overflow-hidden rounded-lg border border-border bg-card shadow-lg">
          <div className="space-y-2 border-b border-border p-2">
            <div className="relative">
              <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-text-muted" />
              <input
                ref={search}
                role="combobox"
                aria-label="Search tills"
                aria-expanded
                aria-controls={listId}
                aria-activedescendant={shown[active] ? `${uid}-o${active}` : undefined}
                placeholder="Search code, branch or address…"
                value={q}
                onChange={(e) => {
                  setQ(e.target.value);
                  setActive(0);
                }}
                onKeyDown={onSearchKey}
                className="h-10 w-full rounded-md border border-border bg-card pr-3 pl-9 text-sm text-text-strong outline-none placeholder:text-text-muted focus-visible:border-bank-accent focus-visible:ring-2 focus-visible:ring-bank-accent/40"
              />
            </div>
            <div
              role="group"
              aria-label="Status filter"
              className="inline-flex rounded-md border border-border bg-surface p-0.5 text-xs font-medium"
            >
              {[
                [true, "Free"],
                [false, "All"],
              ].map(([v, label]) => (
                <button
                  key={String(label)}
                  type="button"
                  aria-pressed={freeOnly === v}
                  onClick={() => {
                    setFreeOnly(v as boolean);
                    setActive(0);
                    search.current?.focus();
                  }}
                  className={cn(
                    "rounded px-3 py-1 outline-none focus-visible:ring-2 focus-visible:ring-bank-accent",
                    freeOnly === v
                      ? "bg-bank-sky-light text-bank-primary"
                      : "text-text-muted hover:text-text-strong",
                  )}
                >
                  {label as string}
                </button>
              ))}
            </div>
          </div>
          <ul id={listId} role="listbox" aria-label="Tills" className="max-h-72 overflow-y-auto">
            {shown.map((t, i) => (
              <li
                key={t.id}
                id={`${uid}-o${i}`}
                role="option"
                aria-selected={t.id === value}
                aria-disabled={!t.available}
                onMouseEnter={() => t.available && setActive(i)}
                onClick={() => pick(t)}
                className={cn(
                  "flex items-center gap-3 px-3 py-2 text-sm",
                  t.available ? "cursor-pointer" : "cursor-not-allowed bg-surface opacity-70",
                  i === active && t.available && "bg-bank-sky-light",
                )}
              >
                <Check
                  className={cn("size-4 shrink-0 text-bank-primary", t.id !== value && "invisible")}
                  aria-hidden
                />
                <span className="w-16 shrink-0 font-mono font-semibold text-text-strong">
                  {t.code}
                </span>
                <span className="min-w-0 flex-1 truncate text-text-body">
                  {t.branch_name}{" "}
                  <span className="text-xs text-text-muted">{t.branch_code}</span>
                  <span className="text-text-muted"> · {t.branch_address || "No address"}</span>
                </span>
                <Status t={t} />
              </li>
            ))}
            {shown.length === 0 && (
              <li className="px-3 py-6 text-center text-sm text-text-muted" role="presentation">
                No tills match
              </li>
            )}
          </ul>
          {matches.length > MAX_SHOWN && (
            <p className="border-t border-border bg-surface px-3 py-1.5 text-xs text-text-muted">
              Refine your search to see more ({matches.length} matches)
            </p>
          )}
        </div>
      )}
    </div>
  );
}
