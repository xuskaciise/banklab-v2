"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";
import { ArrowLeft, Loader2, Plus, Trash2, UserPlus } from "lucide-react";
import { CUSTOMER_TYPES, useCreateCustomer } from "@/lib/customers";
import { useSessionMe } from "@/lib/lab";
import type { PartyIn } from "@/lib/api/types";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  FormActions,
  FormGrid,
  FormSection,
  OptionCards,
} from "@/components/shared/form-layout";
import { EmptyState } from "@/components/shared/empty-state";
import {
  ErrorMsg,
  Labeled,
  PageHeader,
  QueryState,
  ReadOnlyBanner,
} from "@/components/lab/common";
import {
  emptyPerson,
  PersonFields,
  validatePerson,
  type PersonDraft,
} from "@/components/customers/person-fields";

const isOrg = (t: string) => t === "company" || t === "ngo";

function initialPeople(type: string): PersonDraft[] {
  if (type === "individual") return [emptyPerson("owner")];
  if (type === "joint")
    return [emptyPerson("joint_holder"), emptyPerson("joint_holder")];
  return [emptyPerson("signatory")];
}

function relationsFor(type: string) {
  return isOrg(type) ? ["signatory", "director"] : [type === "joint" ? "joint_holder" : "owner"];
}

export default function NewCustomerPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const router = useRouter();
  const me = useSessionMe(sessionId);
  const create = useCreateCustomer(sessionId);
  const [type, setType] = useState("individual");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [address, setAddress] = useState("");
  const [regNo, setRegNo] = useState("");
  const [people, setPeople] = useState<PersonDraft[]>(initialPeople("individual"));
  const [error, setError] = useState<string | null>(null);

  const perms = new Set(me.data?.permissions.map((p) => p.code));
  const readOnly = !!me.data?.read_only;

  function changeType(t: string) {
    setType(t);
    setPeople(initialPeople(t));
    setError(null);
  }

  function submit(ev: React.FormEvent) {
    ev.preventDefault();
    create.reset();
    const label = isOrg(type) ? "Organisation" : "Customer";
    if (!name.trim() && type !== "individual")
      return setError(`${label}: enter the ${isOrg(type) ? "organisation" : "customer"} name`);
    if (!phone.trim()) return setError(`${label}: enter the phone number`);
    if (isOrg(type) && !regNo.trim())
      return setError("Enter the registration number");
    if (type === "joint" && people.length < 2)
      return setError("A joint customer needs at least two joint holders");
    if (isOrg(type) && !people.some((p) => p.relation === "signatory"))
      return setError("Add at least one signatory");
    for (let i = 0; i < people.length; i++) {
      const e = validatePerson(people[i], `Person ${i + 1}`);
      if (e) return setError(e);
    }
    setError(null);
    const parties: PartyIn[] = people.map((p) => ({
      full_name: p.full_name.trim(),
      sex: p.sex,
      date_of_birth: p.date_of_birth,
      phone: p.phone.trim(),
      relation: p.relation,
      ...(p.relation === "director" ? { can_sign: p.can_sign } : {}),
      identity_documents: p.docs.map((d) => ({ ...d, number: d.number.trim() })),
      next_of_kin: p.kin,
    }));
    create.mutate(
      {
        type,
        display_name: name.trim(),
        phone: phone.trim(),
        email: email.trim(),
        address: address.trim(),
        reg_no: isOrg(type) ? regNo.trim() : "",
        parties,
      },
      {
        onSuccess: (c) => {
          toast.success("Customer created");
          router.push(`/s/${sessionId}/customers/${c.id}`);
        },
      },
    );
  }

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6">
      <PageHeader
        title="New customer"
        subtitle="Open a customer information file (CIF)."
        actions={
          <Link
            href={`/s/${sessionId}/customers`}
            className={buttonVariants({ variant: "outline" })}
          >
            <ArrowLeft /> Customers
          </Link>
        }
      />
      <QueryState query={me}>
        {readOnly && <ReadOnlyBanner />}
        {!perms.has("customer.create") || readOnly ? (
          <EmptyState
            title="Not available"
            description="Your role cannot create customers in this session."
          />
        ) : (
          <form onSubmit={submit} noValidate className="space-y-6">
            <FormSection
              title="Customer Type"
              description={
                (type === "individual" && "One owner.") ||
                (type === "joint" && "At least two joint holders; all can sign.") ||
                "Registration number and at least one signatory. Directors are optional."
              }
            >
              <OptionCards
                label="Customer type"
                columns={3}
                options={CUSTOMER_TYPES.map((t) => ({ value: t.value, label: t.label }))}
                value={type}
                onChange={changeType}
              />
            </FormSection>
            <FormSection title="Customer Details">
              <FormGrid>
                <Labeled
                  label={
                    isOrg(type)
                      ? "Organisation name"
                      : type === "individual"
                        ? "Customer name (optional, defaults to owner)"
                        : "Customer name"
                  }
                >
                  <Input value={name} onChange={(e) => setName(e.target.value)} />
                </Labeled>
                <Labeled label="Phone" required>
                  <Input value={phone} onChange={(e) => setPhone(e.target.value)} />
                </Labeled>
                <Labeled label="Email" optional>
                  <Input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </Labeled>
                <Labeled label="Address" optional>
                  <Input value={address} onChange={(e) => setAddress(e.target.value)} />
                </Labeled>
                {isOrg(type) && (
                  <Labeled label="Registration number" required>
                    <Input value={regNo} onChange={(e) => setRegNo(e.target.value)} />
                  </Labeled>
                )}
              </FormGrid>
            </FormSection>

            {people.map((p, i) => (
              <FormSection
                key={i}
                title={
                  type === "individual"
                    ? "Owner"
                    : type === "joint"
                      ? `Joint holder ${i + 1}`
                      : `Person ${i + 1}`
                }
              >
                {type !== "individual" && people.length > (type === "joint" ? 2 : 1) && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="-mt-2 ml-auto flex"
                    onClick={() => setPeople(people.filter((_, j) => j !== i))}
                  >
                    <Trash2 /> Remove
                  </Button>
                )}
                <PersonFields
                  value={p}
                  relationOptions={relationsFor(type)}
                  onChange={(np) => setPeople(people.map((x, j) => (j === i ? np : x)))}
                />
              </FormSection>
            ))}
            {type !== "individual" && (
              <Button
                type="button"
                variant="outline"
                onClick={() =>
                  setPeople([...people, emptyPerson(relationsFor(type)[0])])
                }
              >
                <Plus />{" "}
                {type === "joint" ? "Add joint holder" : "Add signatory / director"}
              </Button>
            )}

            {error && <ErrorMsg error={new Error(error)} />}
            <ErrorMsg error={create.error} />
            <FormActions>
              <Link
                href={`/s/${sessionId}/customers`}
                className={buttonVariants({ variant: "outline" })}
              >
                Cancel
              </Link>
              <Button type="submit" disabled={create.isPending}>
                {create.isPending ? (
                  <Loader2 className="animate-spin" />
                ) : (
                  <UserPlus />
                )}
                {create.isPending ? "Creating…" : "Create customer"}
              </Button>
            </FormActions>
          </form>
        )}
      </QueryState>
    </div>
  );
}
