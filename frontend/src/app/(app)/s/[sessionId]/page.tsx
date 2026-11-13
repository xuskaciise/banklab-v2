"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useSessionMe } from "@/lib/lab";
import { Empty, QueryState, ReadOnlyBanner } from "@/components/lab/common";
import { RoleHome } from "@/components/dashboard/role-home";
import { WelcomeBanner } from "@/components/dashboard/welcome-banner";

export default function RoleHomePage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const me = useSessionMe(sessionId);
  const d = me.data;
  return (
    <div className="w-full space-y-4 p-6">
      <QueryState query={me}>
        {d && (
          <>
            {d.read_only && <ReadOnlyBanner />}
            <WelcomeBanner d={d} />
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
              <RoleHome sid={sessionId} codes={d.permissions.map((p) => p.code)} />
            )}
            <p className="text-sm">
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
