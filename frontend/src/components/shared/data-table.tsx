"use client";

import { useState } from "react";
import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type RowSelectionState,
  type SortingState,
  type VisibilityState,
} from "@tanstack/react-table";
import {
  ArrowDown,
  ArrowUp,
  ChevronLeft,
  ChevronRight,
  ChevronsUpDown,
  Columns3,
  Search,
  SearchX,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input, Select } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { cn } from "@/lib/utils";

declare module "@tanstack/react-table" {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  interface ColumnMeta<TData, TValue> {
    /** Human label used by the column-visibility menu. */
    label?: string;
    /** Extra classes for th and td (e.g. text-right, w-24). */
    className?: string;
  }
}

type Props<T> = {
  columns: ColumnDef<T, any>[]; // eslint-disable-line @typescript-eslint/no-explicit-any
  data: T[] | undefined;
  isLoading?: boolean;
  error?: unknown;
  getRowId?: (row: T) => string;
  searchPlaceholder?: string;
  pageSize?: number;
  initialSort?: SortingState;
  /** Buttons rendered on the right of the toolbar. */
  toolbar?: React.ReactNode;
  emptyTitle: string;
  emptyDescription?: React.ReactNode;
  emptyAction?: React.ReactNode;
  columnToggle?: boolean;
  /** Extra filter controls shown next to the search box. */
  filters?: React.ReactNode;
  rowSelection?: RowSelectionState;
  onRowSelectionChange?: (s: RowSelectionState) => void;
  /** Let cells wrap so the table fits its container instead of scrolling sideways. */
  fit?: boolean;
  /** Hide the built-in client-side search box (when the page searches on the server). */
  hideSearch?: boolean;
};

const PAGE_SIZES = [10, 25, 50];

export function DataTable<T>({
  columns,
  data,
  isLoading,
  error,
  getRowId,
  searchPlaceholder = "Search…",
  pageSize = 10,
  initialSort = [],
  toolbar,
  emptyTitle,
  emptyDescription,
  emptyAction,
  columnToggle = true,
  filters,
  rowSelection,
  onRowSelectionChange,
  fit = false,
  hideSearch = false,
}: Props<T>) {
  const [sorting, setSorting] = useState<SortingState>(initialSort);
  const [globalFilter, setGlobalFilter] = useState("");
  const [visibility, setVisibility] = useState<VisibilityState>({});
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data: data ?? [],
    columns,
    getRowId,
    state: {
      sorting,
      globalFilter,
      columnVisibility: visibility,
      ...(rowSelection ? { rowSelection } : {}),
    },
    enableRowSelection: !!rowSelection,
    onRowSelectionChange: onRowSelectionChange
      ? (u) =>
          onRowSelectionChange(
            typeof u === "function" ? u(rowSelection ?? {}) : u,
          )
      : undefined,
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    onColumnVisibilityChange: setVisibility,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize } },
    globalFilterFn: "includesString",
  });

  if (error) {
    return (
      <p
        role="alert"
        className="rounded-lg bg-fin-danger-bg px-4 py-3 text-sm text-fin-danger"
      >
        {error instanceof Error ? error.message : "Could not load data"}
      </p>
    );
  }

  const total = data?.length ?? 0;
  const filtered = table.getFilteredRowModel().rows.length;
  const { pageIndex, pageSize: size } = table.getState().pagination;
  const from = filtered === 0 ? 0 : pageIndex * size + 1;
  const to = Math.min(filtered, (pageIndex + 1) * size);
  const hideable = table.getAllLeafColumns().filter((c) => c.getCanHide());

  if (!isLoading && total === 0) {
    return (
      <EmptyState
        title={emptyTitle}
        description={emptyDescription}
        action={emptyAction}
      />
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card shadow-xs">
      <div className="flex flex-wrap items-center gap-2 border-b border-border px-3 py-2.5">
        {!hideSearch && (
          <div className="relative min-w-0 flex-1 sm:max-w-xs">
            <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-text-muted" />
            <Input
              aria-label="Search table"
              placeholder={searchPlaceholder}
              value={globalFilter}
              onChange={(e) => setGlobalFilter(e.target.value)}
              className="h-8 pr-8 pl-8"
            />
            {globalFilter && (
              <button
                type="button"
                aria-label="Clear search"
                onClick={() => setGlobalFilter("")}
                className="absolute top-1/2 right-2 -translate-y-1/2 rounded text-text-muted hover:text-text-strong"
              >
                <X className="size-4" />
              </button>
            )}
          </div>
        )}
        {filters}
        <div className="ml-auto flex items-center gap-2">
          {columnToggle && hideable.length > 1 && (
            <DropdownMenu>
              <DropdownMenuTrigger
                render={
                  <Button variant="outline" size="sm">
                    <Columns3 /> Columns
                  </Button>
                }
              />
              <DropdownMenuContent>
                <DropdownMenuLabel>Toggle columns</DropdownMenuLabel>
                {hideable.map((c) => (
                  <DropdownMenuCheckboxItem
                    key={c.id}
                    checked={c.getIsVisible()}
                    onCheckedChange={(v) => c.toggleVisibility(!!v)}
                  >
                    {c.columnDef.meta?.label ??
                      (typeof c.columnDef.header === "string"
                        ? c.columnDef.header
                        : c.id)}
                  </DropdownMenuCheckboxItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          )}
          {toolbar}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table
          className={cn(
            "w-full text-left text-sm text-text-body",
            !fit && "min-w-max",
          )}
        >
          <thead className="bg-surface">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((h) => {
                  const sorted = h.column.getIsSorted();
                  const canSort = h.column.getCanSort();
                  return (
                    <th
                      key={h.id}
                      scope="col"
                      aria-sort={
                        sorted === "asc"
                          ? "ascending"
                          : sorted === "desc"
                            ? "descending"
                            : undefined
                      }
                      className={cn(
                        "border-b border-border px-4 py-2.5 text-xs font-medium tracking-wide whitespace-nowrap text-text-muted uppercase",
                        h.column.columnDef.meta?.className,
                      )}
                    >
                      {h.isPlaceholder ? null : canSort ? (
                        <button
                          type="button"
                          onClick={h.column.getToggleSortingHandler()}
                          className="-mx-1.5 inline-flex items-center gap-1 rounded px-1.5 py-0.5 uppercase hover:bg-hover hover:text-text-strong"
                        >
                          {flexRender(
                            h.column.columnDef.header,
                            h.getContext(),
                          )}
                          {sorted === "asc" ? (
                            <ArrowUp className="size-3" />
                          ) : sorted === "desc" ? (
                            <ArrowDown className="size-3" />
                          ) : (
                            <ChevronsUpDown className="size-3 opacity-50" />
                          )}
                        </button>
                      ) : (
                        flexRender(h.column.columnDef.header, h.getContext())
                      )}
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} aria-hidden="true">
                  {table.getVisibleLeafColumns().map((c) => (
                    <td key={c.id} className="border-b border-border px-4 py-3">
                      <Skeleton className="h-4 w-full max-w-40" />
                    </td>
                  ))}
                </tr>
              ))
            ) : filtered === 0 ? (
              <tr>
                <td colSpan={table.getVisibleLeafColumns().length}>
                  <EmptyState
                    icon={SearchX}
                    title="No matching results"
                    description="Try a different search term."
                    className="rounded-none border-0"
                    action={
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setGlobalFilter("")}
                      >
                        Clear search
                      </Button>
                    }
                  />
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  data-selected={row.getIsSelected() ? "true" : undefined}
                  className="transition-colors hover:bg-hover data-[selected=true]:bg-bank-sky-light/60"
                >
                  {row.getVisibleCells().map((cell) => (
                    <td
                      key={cell.id}
                      className={cn(
                        "border-b border-border px-4 py-3 align-middle",
                        cell.column.columnDef.meta?.className,
                      )}
                    >
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext(),
                      )}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {!isLoading && filtered > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-2.5 text-xs text-text-muted">
          <span>
            Showing {from}–{to} of {filtered}
            {filtered !== total && ` (filtered from ${total})`}
          </span>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2">
              Rows
              <Select
                aria-label="Rows per page"
                value={size}
                onChange={(e) => table.setPageSize(Number(e.target.value))}
                className="h-8 w-[5.5rem] py-0 pr-8 pl-2 text-xs"
              >
                {PAGE_SIZES.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </Select>
            </label>
            <div className="flex items-center gap-1">
              <Button
                variant="outline"
                size="icon-sm"
                aria-label="Previous page"
                disabled={!table.getCanPreviousPage()}
                onClick={() => table.previousPage()}
              >
                <ChevronLeft />
              </Button>
              <span className="min-w-16 text-center tabular-nums">
                {pageIndex + 1} / {Math.max(1, table.getPageCount())}
              </span>
              <Button
                variant="outline"
                size="icon-sm"
                aria-label="Next page"
                disabled={!table.getCanNextPage()}
                onClick={() => table.nextPage()}
              >
                <ChevronRight />
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
