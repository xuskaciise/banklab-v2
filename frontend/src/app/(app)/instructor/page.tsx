"use client";

import Link from "next/link";
import { useQueries } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import type { SessionOut } from "@/lib/api/types";
import { useClasses } from "@/lib/lab";
import { Button } from "@/components/ui/button";
import {
  Empty,
  PageHeader,
  QueryState,
  StatusBadge,
  Table,
  Td,
  Th,
} from "@/components/lab/common";

export default function InstructorDashboard() {
  const classes = useClasses();
  const sessionQueries = useQueries({
    queries: (classes.data ?? []).map((c) => ({
      queryKey: ["class-sessions", c.id],
      queryFn: () => apiFetch<SessionOut[]>(`/api/classes/${c.id}/sessions`),
    })),
  });
  const active = sessionQueries
    .flatMap((q) => q.data ?? [])
    .filter((s) => s.status === "active");

  return (
    <div className="space-y-8">
      <PageHeader
        title="Instructor dashboard"
        actions={
          <Link href="/instructor/classes">
            <Button variant="outline">All classes</Button>
          </Link>
        }
      />
      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-text-strong">My classes</h2>
        <QueryState query={classes}>
          {classes.data?.length ? (
            <Table>
              <thead>
                <tr>
                  <Th>Class</Th>
                  <Th>Code</Th>
                  <Th />
                </tr>
              </thead>
              <tbody>
                {classes.data.map((c) => (
                  <tr key={c.id} className="hover:bg-hover">
                    <Td className="font-medium text-text-strong">{c.name}</Td>
                    <Td>{c.code}</Td>
                    <Td className="text-right">
                      <Link
                        href={`/instructor/classes/${c.id}`}
                        className="text-bank-accent hover:underline"
                      >
                        Open
                      </Link>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          ) : (
            <Empty>
              No classes yet.{" "}
              <Link
                href="/instructor/classes"
                className="text-bank-accent underline"
              >
                Create your first class
              </Link>
            </Empty>
          )}
        </QueryState>
      </section>
      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-text-strong">
          Active sessions
        </h2>
        {active.length ? (
          <Table>
            <thead>
              <tr>
                <Th>Session</Th>
                <Th>Class</Th>
                <Th>Kind</Th>
                <Th>Status</Th>
                <Th />
              </tr>
            </thead>
            <tbody>
              {active.map((s) => (
                <tr key={s.id} className="hover:bg-hover">
                  <Td className="font-medium text-text-strong">{s.name}</Td>
                  <Td>{s.class_name}</Td>
                  <Td className="capitalize">{s.kind}</Td>
                  <Td>
                    <StatusBadge status={s.status} />
                  </Td>
                  <Td className="text-right">
                    <Link
                      href={`/instructor/sessions/${s.id}`}
                      className="text-bank-accent hover:underline"
                    >
                      Control
                    </Link>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        ) : (
          <Empty>No active sessions.</Empty>
        )}
      </section>
    </div>
  );
}
