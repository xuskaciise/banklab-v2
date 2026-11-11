"use client";

import { useRef, useState } from "react";
import { toast } from "sonner";
import { ImagePlus, Trash2 } from "lucide-react";
import {
  useAdminInstitution,
  useLogoSrc,
  useRemoveLogo,
  useUpdateInstitutionName,
  useUploadLogo,
} from "@/lib/admin";
import type { InstitutionOut } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { FormActions, FormSection } from "@/components/shared/form-layout";
import { PageHeader } from "@/components/shared/page-header";
import { ErrorMsg, Labeled, Loading, TextInput, errorText } from "@/components/lab/common";

const MAX_BYTES = 1024 * 1024;
const TYPES = ["image/png", "image/jpeg"];

function NameForm({ inst }: { inst: InstitutionOut }) {
  const update = useUpdateInstitutionName();
  const [name, setName] = useState(inst.name);
  const [error, setError] = useState<string>();

  function submit(ev: React.FormEvent) {
    ev.preventDefault();
    if (!name.trim()) return setError("Enter the institution name");
    setError(undefined);
    update.mutate(name.trim(), { onSuccess: () => toast.success("Institution name saved") });
  }
  return (
    <form onSubmit={submit} noValidate className="space-y-4">
      <Labeled label="Institution name" required error={error}>
        <TextInput value={name} onChange={(e) => setName(e.target.value)} />
      </Labeled>
      <ErrorMsg error={update.error} />
      <FormActions>
        <Button type="submit" disabled={update.isPending || name.trim() === inst.name}>
          {update.isPending ? "Saving…" : "Save name"}
        </Button>
      </FormActions>
    </form>
  );
}

function LogoCard({ inst }: { inst: InstitutionOut }) {
  const upload = useUploadLogo();
  const remove = useRemoveLogo();
  const input = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string>();
  const current = useLogoSrc(inst.logo_url);

  function pick(ev: React.ChangeEvent<HTMLInputElement>) {
    const file = ev.target.files?.[0];
    ev.target.value = "";
    if (!file) return;
    if (!TYPES.includes(file.type)) return setError("The logo must be a PNG or JPG image.");
    if (file.size > MAX_BYTES) return setError("The logo must be 1 MB or smaller.");
    setError(undefined);
    upload.mutate(file, {
      onSuccess: () => toast.success("Logo saved"),
      onError: (e) => toast.error(errorText(e)),
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <span className="flex size-20 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-border bg-white">
          {current ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={current} alt="Institution logo" className="size-full object-contain" />
          ) : (
            <ImagePlus className="size-6 text-text-muted" aria-hidden />
          )}
        </span>
        <p className="text-sm text-text-muted">
          {inst.has_logo
            ? "Shown in the sidebar for every user."
            : "No logo uploaded. The default BankLab logo is shown."}
          <br />
          PNG or JPG, 1 MB or smaller.
        </p>
      </div>
      <input
        ref={input}
        type="file"
        accept="image/png,image/jpeg"
        className="hidden"
        onChange={pick}
      />
      {error && (
        <p role="alert" className="rounded-md bg-fin-danger-bg px-3 py-2 text-sm text-fin-danger">
          {error}
        </p>
      )}
      <ErrorMsg error={remove.error} />
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="outline"
          disabled={upload.isPending}
          onClick={() => input.current?.click()}
        >
          <ImagePlus />{" "}
          {upload.isPending ? "Uploading…" : inst.has_logo ? "Replace logo" : "Upload logo"}
        </Button>
        {inst.has_logo && (
          <Button
            type="button"
            variant="outline"
            disabled={remove.isPending}
            onClick={() =>
              remove.mutate(undefined, { onSuccess: () => toast.success("Logo removed") })
            }
          >
            <Trash2 /> {remove.isPending ? "Removing…" : "Remove logo"}
          </Button>
        )}
      </div>
    </div>
  );
}

export default function InstitutionPage() {
  const q = useAdminInstitution();
  if (q.isPending) return <Loading label="Loading institution" />;
  if (q.isError) return <ErrorMsg error={q.error} />;
  return (
    <div className="mx-auto w-full max-w-3xl space-y-6">
      <PageHeader title="Institution" subtitle="The name and logo shown across BankLab." />
      <FormSection title="Name">
        <NameForm key={q.data.name} inst={q.data} />
      </FormSection>
      <FormSection title="Logo">
        <LogoCard inst={q.data} />
      </FormSection>
    </div>
  );
}
