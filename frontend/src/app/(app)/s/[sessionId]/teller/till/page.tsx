"use client";

import { useParams } from "next/navigation";
import { MyTill } from "@/components/tellers/my-till";

export default function MyTillPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  return <MyTill sid={sessionId} />;
}
