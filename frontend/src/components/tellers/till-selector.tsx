"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ChevronsUpDown, Search, X } from "lucide-react";
import type { TillAvailability } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { FieldLabel } from "@/components/transactions/field-label";
import { TillOption } from "./till-option";
import { usePanelPosition } from "./use-panel-position";

const MAX_SHOWN = 50;

/** Searchable till dropdown (ARIA combobox + listbox) rendered in a portal. */
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
  const trigger = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const search = useRef<HTMLInputElement>(null);
  const selected = tills.find((t) => t.id === value);
  const freeCount = tills.filter((t) => t.available).length;

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

  const pos = usePanelPosition(open, trigger);

  useEffect(() => {
    if (!open) return;
    search.current?.focus();
    const away = (e: MouseEvent) => {
      const n = e.target as Node;
      if (!panel.current?.contains(n) && !trigger.current?.contains(n)) setOpen(false);
    };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, [open, pos !== null]); // eslint-disable-line react-hooks/exhaustive-deps

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
  function goto(j: number) {
    setActive(j);
    document.getElementById(`${uid}-o${j}`)?.scrollIntoView({ block: "nearest" });
  }
  function step(dir: 1 | -1, from: number) {
    for (let j = from + dir; j >= 0 && j < shown.length; j += dir)
      if (shown[j].available) return goto(j);
  }
  function onSearchKey(e: React.KeyboardEvent) {
    const k = e.key;
    if (k === "ArrowDown" || k === "ArrowUp") {
      e.preventDefault();
      step(k === "ArrowDown" ? 1 : -1, active);
    } else if (k === "Home" || k === "End") {
      e.preventDefault();
      if (k === "Home") step(1, -1);
      else step(-1, shown.length);
    } else if (k === "Enter") {
      e.preventDefault();
      if (shown[active]) pick(shown[active]);
    } else if (k === "Escape") {
      e.preventDefault();
      close();
    } else if (k === "Tab") setOpen(false);
  }

  const seg = (v: boolean, label: string, n: number) => (
    <button
      type="button"
      aria-pressed={freeOnly === v}
      onClick={() => {
        setFreeOnly(v);
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
      {label} ({n})
    </button>
  );

  return (
    <div className="space-y-1.5">
      <FieldLabel htmlFor={`${uid}-trigger`} required>
        Till
      </FieldLabel>
      <div className="relative">
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
          className={cn(
            "flex h-11 w-full items-center justify-between gap-2 rounded-lg border border-border bg-card pl-3 text-left text-sm shadow-xs transition-colors outline-none hover:border-text-muted focus-visible:border-bank-accent focus-visible:ring-2 focus-visible:ring-bank-accent/40",
            selected ? "pr-16" : "pr-3",
          )}
        >
          {selected ? (
            <span className="flex min-w-0 items-center gap-2">
              <span className="rounded-md bg-bank-sky-light px-2 py-0.5 font-mono text-xs font-semibold text-bank-primary">
                {selected.code}
              </span>
              <span className="truncate text-text-strong">
                {selected.branch_name}{" "}
                <span className="text-xs text-text-muted">{selected.branch_code}</span>
              </span>
            </span>
          ) : (
            <span className="truncate text-text-muted">Search and select a till…</span>
          )}
          {!selected && (
            <ChevronsUpDown className="size-4 shrink-0 text-text-muted" aria-hidden />
          )}
        </button>
        {selected && (
          <span className="absolute inset-y-0 right-2 flex items-center gap-1">
            <button
              type="button"
              aria-label="Clear till"
              onClick={() => {
                onChange("");
                trigger.current?.focus();
              }}
              className="flex size-7 items-center justify-center rounded-md text-text-muted outline-none hover:bg-hover hover:text-text-strong focus-visible:ring-2 focus-visible:ring-bank-accent"
            >
              <X className="size-4" aria-hidden />
            </button>
            <ChevronsUpDown className="pointer-events-none size-4 text-text-muted" aria-hidden />
          </span>
        )}
      </div>

      {open &&
        pos &&
        createPortal(
          <div
            ref={panel}
            style={{
              position: "fixed",
              left: pos.left,
              width: pos.width,
              top: pos.top,
              bottom: pos.bottom,
              maxHeight: pos.maxH,
            }}
            className="z-[100] flex flex-col overflow-hidden rounded-xl border border-border bg-card shadow-lg"
          >
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
                  className="h-10 w-full rounded-lg border border-border bg-card pr-3 pl-9 text-sm text-text-strong outline-none placeholder:text-text-muted focus-visible:border-bank-accent focus-visible:ring-2 focus-visible:ring-bank-accent/40"
                />
              </div>
              <div
                role="group"
                aria-label="Status filter"
                className="inline-flex rounded-lg border border-border bg-surface p-0.5 text-xs font-medium"
              >
                {seg(true, "Free", freeCount)}
                {seg(false, "All", tills.length)}
              </div>
            </div>
            <ul id={listId} role="listbox" aria-label="Tills" className="min-h-0 flex-1 divide-y divide-border overflow-y-auto">
              {shown.map((t, i) => (
                <TillOption
                  key={t.id}
                  id={`${uid}-o${i}`}
                  t={t}
                  selected={t.id === value}
                  active={i === active}
                  onHover={() => t.available && setActive(i)}
                  onPick={() => pick(t)}
                />
              ))}
              {shown.length === 0 && (
                <li role="presentation" className="px-3 py-8 text-center text-sm text-text-muted">
                  No tills found
                </li>
              )}
            </ul>
            {matches.length > MAX_SHOWN && (
              <p className="border-t border-border bg-surface px-3 py-1.5 text-xs text-text-muted">
                Refine your search to see more ({matches.length} matches)
              </p>
            )}
          </div>,
          document.body,
        )}
    </div>
  );
}
