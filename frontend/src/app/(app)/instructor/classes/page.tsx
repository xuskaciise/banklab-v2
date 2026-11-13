"use client";

import Link from "next/link";
import type { ColumnDef } from "@tanstack/react-table";
import { ArrowRight } from "lucide-react";
import type { ClassOut } from "@/lib/api/types";
import { useClasses } from "@/lib/lab";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/shared/data-table";
import { PageHeader } from "@/components/shared/page-header";
import { CreateClassDialog } from "@/components/lab/create-class-dialog";

const columns: ColumnDef<ClassOut>[] = [
  {
    accessorKey: "name",
    header: "Class",
    cell: ({ row }) => (
      <Link
        href={`/instructor/classes/${row.original.id}`}
        className="font-medium text-text-strong hover:text-bank-accent hover:underline"
      >
        {row.original.name}
      </Link>
    ),
  },
  {
    accessorKey: "code",
    header: "Code",
    cell: ({ getValue }) => (
      <span className="font-mono text-xs text-text-muted">{getValue<string>()}</span>
    ),
  },
  { accessorKey: "instructor_name", header: "Instructor" },
  {
    id: "actions",
    header: () => <span className="sr-only">Actions</span>,
    enableSorting: false,
    enableHiding: false,
    meta: { className: "text-right" },
    cell: ({ row }) => (
      <Link href={`/instructor/classes/${row.original.id}`}>
        <Button size="sm" variant="outline">
          Open <ArrowRight />
        </Button>
      </Link>
    ),
  },
];

export default function ClassesPage() {
  const classes = useClasses();
  return (
    <div>
      <PageHeader
        title="Classes"
        subtitle="Manage your classes, students and sessions."
        actions={<CreateClassDialog />}
      />
      <DataTable
        columns={columns}
        data={classes.data}
        isLoading={classes.isPending}
        error={classes.error}
        getRowId={(c) => c.id}
        searchPlaceholder="Search classes…"
        initialSort={[{ id: "name", desc: false }]}
        emptyTitle="No classes yet"
        emptyDescription="Create your first class to enrol students and open sessions."
        emptyAction={<CreateClassDialog label="Create class" />}
      />
    </div>
  );
}
