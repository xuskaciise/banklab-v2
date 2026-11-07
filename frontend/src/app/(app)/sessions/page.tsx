"use client";

import Link from "next/link";
import { roleLabel, useMySessions } from "@/lib/lab";
import { Button } from "@/components/ui/button";
import {
  Empty,
  PageHeader,
  QueryState,
  Table,
  Td,
  Th,
} from "@/components/lab/common";

export default function MySessionsPage() {
  const sessions = useMySessions();
  return (
    <div>
      <PageHeader title="My sessions" subtitle="Active sessions you are part of." />
      <QueryState query={sessions}>
        {sessions.data?.length ? (
          <Table>
            <thead>
              <tr>
                <Th>Session</Th>
                <Th>Class</Th>
                <Th>Kind</Th>
                <Th>Bank</Th>
                <Th>Role</Th>
                <Th />
              </tr>
            </thead>
            <tbody>
              {sessions.data.map((s) => (
                <tr key={s.session_id} className="hover:bg-hover">
                  <Td className="font-medium text-text-strong">{s.name}</Td>
                  <Td>{s.class_name}</Td>
                  <Td className="capitalize">{s.kind}</Td>
                  <Td>{s.bank_name ?? "Not placed yet"}</Td>
                  <Td>{s.role ? roleLabel(s.role) : "No role yet"}</Td>
                  <Td className="text-right">
                    <Link href={`/s/${s.session_id}`}>
                      <Button size="sm">Open</Button>
                    </Link>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        ) : (
          <Empty>
            You are not in any active session yet. Your instructor will add you
            when a session opens.
          </Empty>
        )}
      </QueryState>
    </div>
  );
}
