"use client";

import Link from "next/link";
import type { ColumnDef } from "@tanstack/react-table";
import { ArrowRight } from "lucide-react";
import type { MySession } from "@/lib/api/types";
import { roleLabel, useMySessions } from "@/lib/lab";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/shared/data-table";
import { PageHeader } from "@/components/shared/page-header";

const columns: ColumnDef<MySession>[] = [
  {
    accessorKey: "name",
    header: "Session",
    cell: ({ row }) => (
      <Link
        href={`/s/${row.original.session_id}`}
        className="font-medium text-text-strong hover:text-bank-accent hover:underline"
      >
        {row.original.name}
      </Link>
    ),
  },
  { accessorKey: "class_name", header: "Class" },
  {
    accessorKey: "kind",
    header: "Kind",
    cell: ({ getValue }) => <span className="capitalize">{getValue<string>()}</span>,
  },
  {
    id: "bank",
    header: "Bank",
    accessorFn: (s) => s.bank_name ?? "Not placed yet",
  },
  {
    id: "role",
    header: "Role",
    accessorFn: (s) => (s.role ? roleLabel(s.role) : "No role yet"),
  },
  {
    id: "actions",
    header: () => <span className="sr-only">Actions</span>,
    enableSorting: false,
    enableHiding: false,
    meta: { className: "text-right" },
    cell: ({ row }) => (
      <Link href={`/s/${row.original.session_id}`}>
        <Button size="sm">
          Open <ArrowRight />
        </Button>
      </Link>
    ),
  },
];

export default function MySessionsPage() {
  const sessions = useMySessions();
  return (
    <div>
      <PageHeader title="My sessions" subtitle="Active sessions you are part of." />
      <DataTable
        columns={columns}
        data={sessions.data}
        isLoading={sessions.isPending}
        error={sessions.error}
        getRowId={(s) => s.session_id}
        searchPlaceholder="Search sessions…"
        emptyTitle="No active sessions yet"
        emptyDescription="Your instructor will add you when a session opens."
      />
    </div>
  );
}
