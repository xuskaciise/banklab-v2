"use client";

import { useParams } from "next/navigation";
import { NewTransaction } from "@/components/transactions/new-transaction";

export default function NewTransactionPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  return <NewTransaction sid={sessionId} />;
}
