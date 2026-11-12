"use client";

import { useParams } from "next/navigation";
import { PageHeader, QueryState } from "@/components/lab/common";
import { StudentExamView } from "@/components/exams/student-exam";
import { useStudentExam } from "@/lib/exams";

export default function StudentExamPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const exam = useStudentExam(sessionId);
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="Exam" />
      <QueryState query={exam}>
        {exam.data && <StudentExamView sid={sessionId} exam={exam.data} />}
      </QueryState>
    </div>
  );
}
