"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { isStudent, useMe } from "@/lib/auth";
import { Loading } from "@/components/lab/common";

/** Staff-only area. The API enforces access; this only redirects students. */
export default function InstructorLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const { data: user } = useMe();
  const student = isStudent(user);
  useEffect(() => {
    if (student) router.replace("/sessions");
  }, [student, router]);
  if (!user || student) return <Loading />;
  return <>{children}</>;
}
