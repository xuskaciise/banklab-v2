"use client";

import { useState } from "react";
import { toast } from "sonner";
import {
  useAddDocument,
  useAddKin,
  useAddParty,
  useUpdateCustomer,
  useUpdateParty,
  RELATION_LABEL,
} from "@/lib/customers";
import type { CustomerDetail, PartyLink } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/shared/checkbox";
import { ErrorMsg, Labeled, Select } from "@/components/lab/common";
import {
  DocFields,
  emptyDoc,
  emptyKin,
  emptyPerson,
  KinFields,
  PersonFields,
  validateDoc,
  validatePerson,
} from "@/components/customers/person-fields";

type Mutation = { isPending: boolean; error: unknown };

function Shell({
  title,
  open,
  onOpenChange,
  onSubmit,
  m,
  localError,
  wide,
  submitLabel = "Save",
  children,
}: {
  title: string;
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onSubmit: () => void;
  m: Mutation;
  localError?: string | null;
  wide?: boolean;
  submitLabel?: string;
  children: React.ReactNode;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className={wide ? "max-w-2xl" : undefined}>
        <form
          noValidate
          className="flex min-h-0 flex-col"
          onSubmit={(e) => {
            e.preventDefault();
            onSubmit();
          }}
        >
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
          </DialogHeader>
          <DialogBody className="space-y-4">
            {children}
            {localError && <ErrorMsg error={new Error(localError)} />}
            <ErrorMsg error={m.error} />
          </DialogBody>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              disabled={m.isPending}
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={m.isPending}>
              {m.isPending ? "Saving…" : submitLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function EditCustomerDialog({
  sessionId,
  customer,
  onClose,
}: {
  sessionId: string;
  customer: CustomerDetail;
  onClose: () => void;
}) {
  const m = useUpdateCustomer(sessionId, customer.id);
  const [name, setName] = useState(customer.display_name);
  const [phone, setPhone] = useState(customer.phone);
  const [email, setEmail] = useState(customer.email);
  const [address, setAddress] = useState(customer.address);
  const [regNo, setRegNo] = useState(customer.reg_no);
  const [err, setErr] = useState<string | null>(null);
  const org = customer.type === "company" || customer.type === "ngo";
  return (
    <Shell
      title="Edit customer"
      open
      onOpenChange={(o) => !o && onClose()}
      m={m}
      localError={err}
      onSubmit={() => {
        if (!name.trim()) return setErr("Enter the customer name");
        setErr(null);
        m.mutate(
          {
            display_name: name.trim(),
            phone: phone.trim(),
            email: email.trim(),
            address: address.trim(),
            ...(org ? { reg_no: regNo.trim() } : {}),
          },
          {
            onSuccess: () => {
              toast.success("Customer updated");
              onClose();
            },
          },
        );
      }}
    >
      <Labeled label="Name">
        <Input value={name} onChange={(e) => setName(e.target.value)} />
      </Labeled>
      <Labeled label="Phone">
        <Input value={phone} onChange={(e) => setPhone(e.target.value)} />
      </Labeled>
      <Labeled label="Email">
        <Input value={email} onChange={(e) => setEmail(e.target.value)} />
      </Labeled>
      <Labeled label="Address">
        <Input value={address} onChange={(e) => setAddress(e.target.value)} />
      </Labeled>
      {org && (
        <Labeled label="Registration number">
          <Input value={regNo} onChange={(e) => setRegNo(e.target.value)} />
        </Labeled>
      )}
    </Shell>
  );
}

export function AddPersonDialog({
  sessionId,
  customer,
  onClose,
}: {
  sessionId: string;
  customer: CustomerDetail;
  onClose: () => void;
}) {
  const m = useAddParty(sessionId, customer.id);
  const org = customer.type === "company" || customer.type === "ngo";
  const relations = org
    ? ["signatory", "director"]
    : [customer.type === "joint" ? "joint_holder" : "owner"];
  const [p, setP] = useState(emptyPerson(relations[0]));
  const [err, setErr] = useState<string | null>(null);
  return (
    <Shell
      title="Add person"
      wide
      open
      onOpenChange={(o) => !o && onClose()}
      m={m}
      localError={err}
      submitLabel="Add person"
      onSubmit={() => {
        const e = validatePerson(p, "Person");
        setErr(e);
        if (e) return;
        m.mutate(
          {
            relation: p.relation,
            ...(p.relation === "director" ? { can_sign: p.can_sign } : {}),
            full_name: p.full_name.trim(),
            sex: p.sex,
            date_of_birth: p.date_of_birth,
            phone: p.phone.trim(),
            mother_name: "",
            guardian_phone: "",
            identity_documents: p.docs,
            next_of_kin: p.kin,
          },
          {
            onSuccess: () => {
              toast.success("Person added");
              onClose();
            },
          },
        );
      }}
    >
      <PersonFields value={p} onChange={setP} relationOptions={relations} />
    </Shell>
  );
}

export function EditPersonDialog({
  sessionId,
  customerId,
  party,
  family = false,
  onClose,
}: {
  sessionId: string;
  customerId: string;
  party: PartyLink;
  /** True when the party is the owner of an individual customer. */
  family?: boolean;
  onClose: () => void;
}) {
  const m = useUpdateParty(sessionId, customerId);
  const [name, setName] = useState(party.full_name);
  const [sex, setSex] = useState(party.sex);
  const [dob, setDob] = useState(party.date_of_birth ?? "");
  const [phone, setPhone] = useState(party.phone);
  const [mother, setMother] = useState(party.mother_name);
  const [guardian, setGuardian] = useState(party.guardian_phone);
  const [canSign, setCanSign] = useState(party.can_sign);
  const [err, setErr] = useState<string | null>(null);
  const fixed = party.relation !== "director";
  return (
    <Shell
      title={`Edit ${party.full_name}`}
      open
      onOpenChange={(o) => !o && onClose()}
      m={m}
      localError={err}
      onSubmit={() => {
        if (!name.trim()) return setErr("Enter the full name");
        setErr(null);
        m.mutate(
          {
            id: party.party_id,
            full_name: name.trim(),
            sex,
            date_of_birth: dob || null,
            phone: phone.trim(),
            ...(family
              ? { mother_name: mother.trim(), guardian_phone: guardian.trim() }
              : {}),
            ...(fixed ? {} : { can_sign: canSign }),
          },
          {
            onSuccess: () => {
              toast.success("Person updated");
              onClose();
            },
          },
        );
      }}
    >
      <Labeled label="Full name">
        <Input value={name} onChange={(e) => setName(e.target.value)} />
      </Labeled>
      <Labeled label="Sex">
        <Select className="w-full" value={sex} onChange={(e) => setSex(e.target.value)}>
          <option value="">Select…</option>
          <option value="male">Male</option>
          <option value="female">Female</option>
        </Select>
      </Labeled>
      <Labeled label="Date of birth">
        <Input type="date" value={dob} onChange={(e) => setDob(e.target.value)} />
      </Labeled>
      <Labeled label="Phone">
        <Input value={phone} onChange={(e) => setPhone(e.target.value)} />
      </Labeled>
      {family && (
        <>
          <Labeled label="Mother's name">
            <Input value={mother} onChange={(e) => setMother(e.target.value)} />
          </Labeled>
          <Labeled label="Parent/guardian phone">
            <Input value={guardian} onChange={(e) => setGuardian(e.target.value)} />
          </Labeled>
        </>
      )}
      {fixed ? (
        <p className="text-xs text-text-muted">
          {RELATION_LABEL[party.relation] ?? party.relation} can always sign.
        </p>
      ) : (
        <label className="flex items-center gap-2 text-sm text-text-strong">
          <Checkbox checked={canSign} onChange={(e) => setCanSign(e.target.checked)} />
          Can sign
        </label>
      )}
    </Shell>
  );
}

export function AddDocumentDialog({
  sessionId,
  customerId,
  party,
  onClose,
}: {
  sessionId: string;
  customerId: string;
  party: PartyLink;
  onClose: () => void;
}) {
  const m = useAddDocument(sessionId, customerId);
  const [d, setD] = useState(emptyDoc());
  const [err, setErr] = useState<string | null>(null);
  return (
    <Shell
      title={`Add ID document for ${party.full_name}`}
      open
      onOpenChange={(o) => !o && onClose()}
      m={m}
      localError={err}
      onSubmit={() => {
        const e = validateDoc(d);
        setErr(e);
        if (e) return;
        m.mutate(
          { ...d, number: d.number.trim(), partyId: party.party_id },
          {
            onSuccess: () => {
              toast.success("ID document added");
              onClose();
            },
          },
        );
      }}
    >
      <DocFields value={d} onChange={setD} />
    </Shell>
  );
}

export function AddKinDialog({
  sessionId,
  customerId,
  party,
  onClose,
}: {
  sessionId: string;
  customerId: string;
  party: PartyLink;
  onClose: () => void;
}) {
  const m = useAddKin(sessionId, customerId);
  const [k, setK] = useState(emptyKin());
  const [err, setErr] = useState<string | null>(null);
  return (
    <Shell
      title={`Add next of kin for ${party.full_name}`}
      wide
      open
      onOpenChange={(o) => !o && onClose()}
      m={m}
      localError={err}
      onSubmit={() => {
        if (!k.name.trim() || !k.phone.trim() || !k.relationship.trim())
          return setErr("Enter the name, phone and relationship");
        setErr(null);
        m.mutate(
          { ...k, partyId: party.party_id },
          {
            onSuccess: () => {
              toast.success("Next of kin added");
              onClose();
            },
          },
        );
      }}
    >
      <KinFields value={k} onChange={setK} />
    </Shell>
  );
}
