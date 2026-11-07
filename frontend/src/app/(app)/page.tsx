"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { isStudent, useMe } from "@/lib/auth";
import { Loading } from "@/components/lab/common";

export default function Home() {
  const router = useRouter();
  const { data: user } = useMe();
  useEffect(() => {
    if (user) router.replace(isStudent(user) ? "/sessions" : "/instructor");
  }, [user, router]);
  return <Loading />;
}
