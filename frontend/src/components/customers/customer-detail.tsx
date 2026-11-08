"use client";

import { useRef, useState } from "react";
import { toast } from "sonner";
import { FileText, ImageIcon, Pencil, Plus, Upload } from "lucide-react";
import {
  docLabel,
  formatCif,
  RELATION_LABEL,
  scopeBase,
  typeLabel,
  useBlobUrl,
  useCustomer,
  useUploadFile,
  type CustomerScope,
} from "@/lib/customers";
import { apiBlob } from "@/lib/api/client";
import { formatDateTime } from "@/lib/lab";
import type { DocumentOut, PartyLink } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/shared/status-badge";
import { CustomerAccounts } from "@/components/accounts/customer-accounts";
import { QueryState, errorText } from "@/components/lab/common";
import {
  AddDocumentDialog,
  AddKinDialog,
  AddPersonDialog,
  EditCustomerDialog,
  EditPersonDialog,
} from "@/components/customers/customer-dialogs";

const MAX_BYTES = 2 * 1024 * 1024;

function PickFile({
  label,
  accept,
  maxBytes,
  pending,
  onFile,
}: {
  label: string;
  accept: string;
  maxBytes?: number;
  pending: boolean;
  onFile: (f: File) => void;
}) {
  const ref = useRef<HTMLInputElement>(null);
  return (
    <>
      <input
        ref={ref}
        type="file"
        accept={accept}
        className="hidden"
        aria-label={label}
        tabIndex={-1}
        onChange={(e) => {
          const f = e.target.files?.[0];
          e.target.value = "";
          if (!f) return;
          if (maxBytes && f.size > maxBytes) {
            toast.error("File is too large (maximum 2 MB)");
            return;
          }
          onFile(f);
        }}
      />
      <Button
        type="button"
        size="sm"
        variant="outline"
        disabled={pending}
        onClick={() => ref.current?.click()}
      >
        <Upload /> {pending ? "Uploading…" : label}
      </Button>
    </>
  );
}

function Thumb({
  scope,
  customerId,
  party,
  kind,
  canEdit,
}: {
  scope: CustomerScope;
  customerId: string;
  party: PartyLink;
  kind: "photo" | "signature";
  canEdit: boolean;
}) {
  const has = kind === "photo" ? party.has_photo : party.has_signature;
  const student = scope.kind === "student";
  const [ver, setVer] = useState(0);
  const path = `${scopeBase(scope)}/${customerId}/parties/${party.party_id}/${kind}`;
  const img = useBlobUrl(path, student && has, ver);
  const up = useUploadFile(
    scope.sessionId,
    customerId,
  );
  const title = kind === "photo" ? "Photo" : "Signature";
  return (
    <div className="space-y-2">
      <p className="text-xs font-medium tracking-wide text-text-muted uppercase">
        {title}
      </p>
      <div className="flex h-24 w-32 items-center justify-center overflow-hidden rounded-lg border border-border bg-surface">
        {img.data ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={img.data}
            alt={`${title} of ${party.full_name}`}
            className="size-full object-contain"
          />
        ) : (
          <span className="flex flex-col items-center gap-1 text-xs text-text-muted">
            <ImageIcon className="size-5" />
            {has ? (img.isError ? "Unavailable" : student ? "Loading…" : "On file") : "None"}
          </span>
        )}
      </div>
      {canEdit && (
        <PickFile
          label={has ? `Replace ${kind}` : `Upload ${kind}`}
          accept="image/jpeg,image/png"
          maxBytes={MAX_BYTES}
          pending={up.isPending}
          onFile={(file) =>
            up.mutate(
              { path: `parties/${party.party_id}/${kind}`, file },
              {
                onSuccess: () => {
                  setVer((v) => v + 1);
                  toast.success(`${title} saved`);
                },
                onError: (e) => toast.error(errorText(e)),
              },
            )
          }
        />
      )}
    </div>
  );
}

function DocRow({
  scope,
  customerId,
  partyId,
  doc,
  canEdit,
}: {
  scope: CustomerScope;
  customerId: string;
  partyId: string;
  doc: DocumentOut;
  canEdit: boolean;
}) {
  const up = useUploadFile(scope.sessionId, customerId);
  const [opening, setOpening] = useState(false);
  const fileRel = `parties/${partyId}/documents/${doc.id}/file`;
  async function view() {
    setOpening(true);
    try {
      const blob = await apiBlob(`${scopeBase(scope)}/${customerId}/${fileRel}`);
      window.open(URL.createObjectURL(blob), "_blank", "noopener");
    } catch (e) {
      toast.error(errorText(e));
    } finally {
      setOpening(false);
    }
  }
  return (
    <tr className="hover:bg-hover">
      <td className="border-b border-border px-3 py-2">{docLabel(doc.type)}</td>
      <td className="border-b border-border px-3 py-2 font-mono text-xs">
        {doc.number}
      </td>
      <td className="border-b border-border px-3 py-2 whitespace-nowrap tabular-nums">
        {doc.issue_date} → {doc.expiry_date}
      </td>
      <td className="border-b border-border px-3 py-2">
        <div className="flex flex-wrap items-center justify-end gap-2">
          {doc.has_file ? (
            scope.kind === "student" ? (
              <Button size="sm" variant="ghost" disabled={opening} onClick={view}>
                <FileText /> View file
              </Button>
            ) : (
              <StatusBadge status="active" label="File on record" />
            )
          ) : (
            <span className="text-xs text-text-muted">No file</span>
          )}
          {canEdit && (
            <PickFile
              label={doc.has_file ? "Replace file" : "Upload file"}
              accept="image/jpeg,image/png,application/pdf"
              pending={up.isPending}
              onFile={(file) =>
                up.mutate(
                  { path: fileRel, file },
                  {
                    onSuccess: () => toast.success("Document file saved"),
                    onError: (e) => toast.error(errorText(e)),
                  },
                )
              }
            />
          )}
        </div>
      </td>
    </tr>
  );
}

function PartyCard({
  scope,
  customerId,
  party,
  canEdit,
  onEdit,
  onAddDoc,
  onAddKin,
}: {
  scope: CustomerScope;
  customerId: string;
  party: PartyLink;
  canEdit: boolean;
  onEdit: () => void;
  onAddDoc: () => void;
  onAddKin: () => void;
}) {
  return (
    <section className="space-y-4 rounded-xl border border-border bg-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-base font-semibold text-text-strong">
            {party.full_name}
          </p>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-text-muted">
            <StatusBadge
              status={party.relation}
              label={RELATION_LABEL[party.relation] ?? party.relation}
              tone="info"
            />
            <StatusBadge
              status={party.can_sign ? "active" : "inactive"}
              label={party.can_sign ? "Can sign" : "Cannot sign"}
            />
            <span className="capitalize">{party.sex || "—"}</span>
            <span>· Born {party.date_of_birth ?? "—"}</span>
            <span>· {party.phone || "—"}</span>
          </p>
        </div>
        {canEdit && (
          <Button size="sm" variant="outline" onClick={onEdit}>
            <Pencil /> Edit person
          </Button>
        )}
      </div>

      <div className="flex flex-wrap gap-6">
        <Thumb scope={scope} customerId={customerId} party={party} kind="photo" canEdit={canEdit} />
        <Thumb scope={scope} customerId={customerId} party={party} kind="signature" canEdit={canEdit} />
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium tracking-wide text-text-muted uppercase">
            ID documents
          </p>
          {canEdit && (
            <Button size="sm" variant="outline" onClick={onAddDoc}>
              <Plus /> Add document
            </Button>
          )}
        </div>
        {party.identity_documents.length ? (
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full min-w-max text-left text-sm text-text-body">
              <tbody>
                {party.identity_documents.map((d) => (
                  <DocRow
                    key={d.id}
                    scope={scope}
                    customerId={customerId}
                    partyId={party.party_id}
                    doc={d}
                    canEdit={canEdit}
                  />
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-text-muted">No ID documents.</p>
        )}
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium tracking-wide text-text-muted uppercase">
            Next of kin
          </p>
          {canEdit && (
            <Button size="sm" variant="outline" onClick={onAddKin}>
              <Plus /> Add next of kin
            </Button>
          )}
        </div>
        {party.next_of_kin.length ? (
          <ul className="space-y-1 text-sm">
            {party.next_of_kin.map((k) => (
              <li key={k.id}>
                <span className="font-medium text-text-strong">{k.name}</span>{" "}
                <span className="text-text-muted">
                  · {k.relationship} · {k.phone}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-text-muted">None recorded.</p>
        )}
      </div>
    </section>
  );
}

export function CustomerDetailView({
  scope,
  id,
  canEdit,
  accounts,
  enabled = true,
}: {
  scope: CustomerScope;
  id: string;
  /** Student with customer.update on a non-archived session. */
  canEdit: boolean;
  /** Student only: shows the Accounts section (account.view / account.open). */
  accounts?: { canOpen: boolean };
  enabled?: boolean;
}) {
  const q = useCustomer(scope, id, enabled);
  const [dlg, setDlg] = useState<
    | { kind: "edit" }
    | { kind: "addPerson" }
    | { kind: "person" | "doc" | "kin"; partyId: string }
    | null
  >(null);
  const c = q.data;
  const party = (pid: string) => c?.parties.find((p) => p.party_id === pid);
  const close = () => setDlg(null);
  const org = c && (c.type === "company" || c.type === "ngo");
  return (
    <QueryState query={q}>
      {c && (
        <div className="space-y-6">
          <section className="flex flex-wrap items-start justify-between gap-4 rounded-xl border border-border bg-card p-5">
            <div className="min-w-0 space-y-2">
              <p className="font-mono text-xs text-text-muted">
                CIF {formatCif(c.cif_no)}
              </p>
              <h2 className="flex flex-wrap items-center gap-3 text-xl font-semibold text-text-strong">
                {c.display_name}
                <StatusBadge status={c.type} label={typeLabel(c.type)} tone="info" />
                <StatusBadge
                  status={c.kyc_complete ? "kyc_complete" : "kyc_incomplete"}
                  label={c.kyc_complete ? "KYC complete" : "KYC incomplete"}
                  tone={c.kyc_complete ? "success" : "pending"}
                />
              </h2>
              <dl className="grid gap-x-8 gap-y-1 text-sm sm:grid-cols-2">
                <div><dt className="inline text-text-muted">Phone: </dt><dd className="inline">{c.phone || "—"}</dd></div>
                <div><dt className="inline text-text-muted">Email: </dt><dd className="inline">{c.email || "—"}</dd></div>
                <div><dt className="inline text-text-muted">Address: </dt><dd className="inline">{c.address || "—"}</dd></div>
                {org && (
                  <div><dt className="inline text-text-muted">Reg. no: </dt><dd className="inline">{c.reg_no || "—"}</dd></div>
                )}
                <div><dt className="inline text-text-muted">Created: </dt><dd className="inline">{formatDateTime(c.created_at)}</dd></div>
              </dl>
            </div>
            {canEdit && (
              <Button variant="outline" onClick={() => setDlg({ kind: "edit" })}>
                <Pencil /> Edit
              </Button>
            )}
          </section>

          {!c.kyc_complete && (
            <section className="space-y-2 rounded-xl border border-border bg-fin-pending-bg p-4">
              <h2 className="text-sm font-semibold text-fin-pending">
                KYC incomplete: an account cannot be opened until these are added
              </h2>
              <ul className="list-disc space-y-1 pl-5 text-sm text-text-body">
                {c.kyc_missing.map((m) => (
                  <li key={`${m.code}-${m.party_id ?? "customer"}`}>{m.label}</li>
                ))}
              </ul>
            </section>
          )}

          {scope.kind === "student" && accounts && (
            <CustomerAccounts
              sessionId={scope.sessionId}
              customerId={c.id}
              canOpen={accounts.canOpen}
            />
          )}

          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-text-strong">
              People ({c.parties.length})
            </h2>
            {canEdit && (
              <Button onClick={() => setDlg({ kind: "addPerson" })}>
                <Plus /> Add person
              </Button>
            )}
          </div>
          {c.parties.length ? (
            c.parties.map((p) => (
              <PartyCard
                key={p.party_id}
                scope={scope}
                customerId={c.id}
                party={p}
                canEdit={canEdit}
                onEdit={() => setDlg({ kind: "person", partyId: p.party_id })}
                onAddDoc={() => setDlg({ kind: "doc", partyId: p.party_id })}
                onAddKin={() => setDlg({ kind: "kin", partyId: p.party_id })}
              />
            ))
          ) : (
            <p className="text-sm text-text-muted">No people linked.</p>
          )}

          {scope.kind === "student" && dlg?.kind === "edit" && (
            <EditCustomerDialog sessionId={scope.sessionId} customer={c} onClose={close} />
          )}
          {scope.kind === "student" && dlg?.kind === "addPerson" && (
            <AddPersonDialog sessionId={scope.sessionId} customer={c} onClose={close} />
          )}
          {scope.kind === "student" && dlg && "partyId" in dlg && party(dlg.partyId) && (
            <>
              {dlg.kind === "person" && (
                <EditPersonDialog
                  sessionId={scope.sessionId}
                  customerId={c.id}
                  party={party(dlg.partyId)!}
                  onClose={close}
                />
              )}
              {dlg.kind === "doc" && (
                <AddDocumentDialog
                  sessionId={scope.sessionId}
                  customerId={c.id}
                  party={party(dlg.partyId)!}
                  onClose={close}
                />
              )}
              {dlg.kind === "kin" && (
                <AddKinDialog
                  sessionId={scope.sessionId}
                  customerId={c.id}
                  party={party(dlg.partyId)!}
                  onClose={close}
                />
              )}
            </>
          )}
        </div>
      )}
    </QueryState>
  );
}

