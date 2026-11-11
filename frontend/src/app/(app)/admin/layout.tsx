"use client";

import { useMe } from "@/lib/auth";
import { EmptyState } from "@/components/shared/empty-state";
import { Loading } from "@/components/lab/common";

/** Admin-only area. The API enforces the role; others just see "No access". */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { data: user } = useMe();
  if (!user) return <Loading />;
  if (user.platform_role !== "admin")
    return <EmptyState title="No access" description="Only a platform admin can open this area." />;
  return <>{children}</>;
}
