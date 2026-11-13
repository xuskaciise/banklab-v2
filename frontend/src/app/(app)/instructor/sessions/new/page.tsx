"use client";

import { Suspense } from "react";
import { toast } from "sonner";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCreateSession } from "@/lib/lab";
import { Plus } from "lucide-react";
import { BASE_VALUES, SessionForm } from "@/components/lab/session-form";
import { Loading } from "@/components/lab/common";

function Wizard({ classId }: { classId: string }) {
  const router = useRouter();
  const create = useCreateSession();
  return (
    <SessionForm
      classId={classId}
      initial={BASE_VALUES}
      title="Open new session"
      subtitle="The session is created as a draft. Open it from its control page once members are ready."
      submitLabel="Create session"
      pendingLabel="Creating…"
      submitIcon={<Plus className="size-4" aria-hidden />}
      pending={create.isPending}
      error={create.error}
      cancelHref="/instructor/classes"
      onSubmit={(v, templateId) =>
        create.mutate(
          {
            class_id: classId,
            name: v.name,
            template_id: templateId || null,
            kind: v.kind,
            structure: v.structure,
            allowed_roles: v.roles,
            default_visibility: v.visibility,
            learning_panel: v.panel,
            seed_profile: v.seedProfile,
            opening_capital_usd: v.capUsd,
            opening_capital_sos: v.capSos,
          },
          {
            onSuccess: (s) => {
              toast.success(`Session "${s.name}" created as draft`);
              router.push(`/instructor/sessions/${s.id}`);
            },
          },
        )
      }
    />
  );
}

function WizardEntry() {
  const classId = useSearchParams().get("classId");
  if (!classId)
    return (
      <p className="text-sm text-text-muted">
        Choose a class first.{" "}
        <Link href="/instructor/classes" className="text-bank-accent underline">
          Go to classes
        </Link>
      </p>
    );
  return <Wizard classId={classId} />;
}

export default function NewSessionPage() {
  return (
    <Suspense fallback={<Loading />}>
      <WizardEntry />
    </Suspense>
  );
}
