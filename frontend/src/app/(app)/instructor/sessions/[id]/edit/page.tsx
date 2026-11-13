"use client";

import { toast } from "sonner";
import { useParams, useRouter } from "next/navigation";
import { Save } from "lucide-react";
import { useSession, useUpdateSession } from "@/lib/lab";
import { QueryState, ReadOnlyBanner } from "@/components/lab/common";
import { SessionForm, valuesFromSession } from "@/components/lab/session-form";

export default function EditSessionPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const session = useSession(id);
  const update = useUpdateSession(id);
  const s = session.data;
  const back = `/instructor/sessions/${id}`;
  return (
    <QueryState query={session}>
      {s && (
        <>
          {s.status === "archived" && <ReadOnlyBanner />}
          <SessionForm
            key={s.id}
            classId={s.class_id}
            initial={valuesFromSession(s)}
            initialTemplateId={s.template_id ?? ""}
            locked={s.locked_fields}
            archived={s.status === "archived"}
            title={`Edit session: ${s.name}`}
            subtitle={
              s.status === "active"
                ? "The session is open, so some settings are locked."
                : "Changes apply to this draft session."
            }
            submitLabel="Save changes"
            pendingLabel="Saving…"
            submitIcon={<Save className="size-4" aria-hidden />}
            pending={update.isPending}
            error={update.error}
            cancelHref={back}
            onSubmit={(v, templateId) =>
              update.mutate(
                {
                  name: v.name,
                  kind: v.kind,
                  structure: v.structure,
                  allowed_roles: v.roles,
                  default_visibility: v.visibility,
                  learning_panel: v.panel,
                  seed_profile: v.seedProfile,
                  opening_capital_usd: v.capUsd,
                  opening_capital_sos: v.capSos,
                  ...(templateId
                    ? { template_id: templateId, clear_template: false }
                    : { clear_template: !!s.template_id }),
                },
                {
                  onSuccess: () => {
                    toast.success("Session updated");
                    router.push(back);
                  },
                },
              )
            }
          />
        </>
      )}
    </QueryState>
  );
}
