"use client";

import { toast } from "sonner";
import { AlertTriangle } from "lucide-react";
import { useMe } from "@/lib/auth";
import { usePlatformSettings, useUpdatePlatformSettings } from "@/lib/platform";
import { EmptyState } from "@/components/shared/empty-state";
import { FormSection } from "@/components/shared/form-layout";
import { PageHeader } from "@/components/shared/page-header";
import { ErrorMsg, Loading } from "@/components/lab/common";
import { SwitchRow } from "@/components/lab/roles-field";

/** Admin-only. The API enforces the role; non-admins just see "No access". */
export default function PlatformSettingsPage() {
  const { data: user } = useMe();
  const settings = usePlatformSettings();
  const update = useUpdatePlatformSettings();

  if (user && user.platform_role !== "admin")
    return (
      <EmptyState title="No access" description="Only a platform admin can change these settings." />
    );
  if (settings.isPending) return <Loading label="Loading settings" />;
  if (settings.isError) return <ErrorMsg error={settings.error} />;

  const on = settings.data.sos_enabled;
  return (
    <div className="mx-auto w-full max-w-3xl space-y-6">
      <PageHeader title="Platform settings" subtitle="Options that apply to the whole platform." />
      <FormSection title="Currencies">
        <SwitchRow
          title="Somali shilling (SOS)"
          description={`SOS is ${on ? "on" : "off"}. USD is always available. When SOS is off, no new SOS activity can be created; existing SOS balances and history stay visible.`}
          checked={on}
          disabled={update.isPending}
          onChange={(v) =>
            update.mutate(
              { sos_enabled: v },
              {
                onSuccess: () => toast.success(`SOS turned ${v ? "on" : "off"}`),
                onError: (e) => toast.error(e.message),
              },
            )
          }
        />
        <p className="flex gap-2.5 rounded-lg border border-fin-pending/30 bg-card p-3 text-sm leading-relaxed text-text-body">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-fin-pending" aria-hidden />
          This setting is global. It takes effect immediately for all running sessions
          and all banks.
        </p>
        <ErrorMsg error={update.error} />
      </FormSection>
    </div>
  );
}
