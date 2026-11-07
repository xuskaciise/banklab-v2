"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { roleLabel, useSessionMe } from "@/lib/lab";
import {
  Empty,
  PageHeader,
  QueryState,
  ReadOnlyBanner,
  Table,
  Td,
  Th,
} from "@/components/lab/common";
import { Badge } from "@/components/ui/badge";

export default function RoleHomePage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const me = useSessionMe(sessionId);
  const d = me.data;
  return (
    <div>
      <QueryState query={me}>
        {d && (
          <>
            {d.read_only && <ReadOnlyBanner />}
            <PageHeader
              title={d.session_name}
              subtitle={`${d.class_name} · ${d.kind === "exam" ? "Exam" : "Practice"}`}
            />
            {!d.bank_id ? (
              <Empty>
                You have not been placed in a bank yet. Your instructor will
                assign you shortly.
              </Empty>
            ) : !d.role ? (
              <Empty>
                You are in {d.bank_name} but have no role yet. Your instructor
                will assign one.
              </Empty>
            ) : (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="text-sm text-text-muted">Your role</span>
                  <Badge className="bg-bank-sky-light text-bank-primary">
                    {roleLabel(d.role)}
                  </Badge>
                  <span className="text-sm text-text-muted">
                    Visibility:{" "}
                    <span className="text-text-strong">
                      {d.visibility === "own" ? "Own work only" : "Whole bank"}
                    </span>
                  </span>
                </div>
                <p className="text-sm text-text-muted">
                  Banking screens for your role are coming soon. Here is what
                  you will be allowed to do.
                </p>
                {d.permissions.length ? (
                  <Table>
                    <thead>
                      <tr>
                        <Th>Permission</Th>
                        <Th>Scope</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {d.permissions.map((p) => (
                        <tr key={p.code} className="hover:bg-hover">
                          <Td className="font-mono text-xs">{p.code}</Td>
                          <Td>
                            {p.scope === "own" ? "Own work only" : "Whole bank"}
                          </Td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                ) : (
                  <Empty>Your role has no permissions in this session.</Empty>
                )}
              </div>
            )}
            <p className="mt-6 text-sm">
              <Link href="/sessions" className="text-bank-accent hover:underline">
                Back to my sessions
              </Link>
            </p>
          </>
        )}
      </QueryState>
    </div>
  );
}
