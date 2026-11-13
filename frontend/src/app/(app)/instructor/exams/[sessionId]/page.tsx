"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useSession } from "@/lib/lab";
import { useExam } from "@/lib/exams";
import { Button } from "@/components/ui/button";
import { PageHeader, QueryState } from "@/components/lab/common";
import { ExamSetup } from "@/components/exams/exam-setup";

export default function ExamSetupPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const session = useSession(sessionId);
  const exam = useExam(sessionId);
  return (
    <div>
      <PageHeader
        title="Exam setup"
        subtitle={session.data ? `${session.data.name} · ${session.data.class_name}` : undefined}
        actions={
          <>
            <Button variant="outline" nativeButton={false} render={<Link href={`/instructor/sessions/${sessionId}`} />}>
              Session
            </Button>
            {exam.data?.status === "published" && (
              <Button variant="outline" nativeButton={false} render={<Link href={`/instructor/exams/${sessionId}/results`} />}>
                Results
              </Button>
            )}
          </>
        }
      />
      <QueryState query={exam}>
        <ExamSetup sid={sessionId} exam={exam.data ?? null} />
      </QueryState>
    </div>
  );
}
