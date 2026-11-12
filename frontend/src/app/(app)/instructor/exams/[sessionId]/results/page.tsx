"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useSession } from "@/lib/lab";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/lab/common";
import { ExamResultsView } from "@/components/exams/exam-results";

export default function ExamResultsPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const session = useSession(sessionId);
  return (
    <div>
      <PageHeader
        title="Exam results"
        subtitle={session.data ? `${session.data.name} · ${session.data.class_name}` : undefined}
        actions={
          <Button variant="outline" nativeButton={false} render={<Link href={`/instructor/exams/${sessionId}`} />}>
            Exam setup
          </Button>
        }
      />
      <ExamResultsView sid={sessionId} />
    </div>
  );
}
