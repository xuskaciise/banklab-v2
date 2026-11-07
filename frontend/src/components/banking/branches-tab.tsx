"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Building2, Pencil, Plus } from "lucide-react";
import type { BankOut, BranchOut, SessionOut } from "@/lib/api/types";
import { useBanks } from "@/lib/lab";
import {
  useBranches,
  useCreateBranch,
  useCreateTill,
  useTills,
  useUpdateBranch,
} from "@/lib/banking";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorMsg, Labeled, QueryState } from "@/components/lab/common";

function BranchDialog({
  sessionId,
  bankId,
  branch,
  open,
  onOpenChange,
}: {
  sessionId: string;
  bankId: string;
  branch?: BranchOut;
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const create = useCreateBranch(sessionId, bankId);
  const update = useUpdateBranch(sessionId, bankId);
  const [code, setCode] = useState(branch?.code ?? "");
  const [name, setName] = useState(branch?.name ?? "");
  const [address, setAddress] = useState(branch?.address ?? "");
  const [errors, setErrors] = useState<{ code?: string; name?: string }>({});
  const m = branch ? update : create;

  function submit(ev: React.FormEvent) {
    ev.preventDefault();
    const next = {
      code: !branch && !code.trim() ? "Enter a branch code" : undefined,
      name: name.trim() ? undefined : "Enter a branch name",
    };
    setErrors(next);
    if (next.code || next.name) return;
    const done = {
      onSuccess: () => {
        toast.success(branch ? "Branch updated" : "Branch created");
        onOpenChange(false);
      },
    };
    if (branch)
      update.mutate(
        { id: branch.id, name: name.trim(), address: address.trim() },
        done,
      );
    else
      create.mutate(
        { code: code.trim(), name: name.trim(), address: address.trim() },
        done,
      );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={submit} noValidate className="space-y-4">
          <DialogHeader>
            <DialogTitle>{branch ? "Edit branch" : "Create branch"}</DialogTitle>
          </DialogHeader>
          <Labeled
            label="Code"
            error={errors.code}
            hint={branch ? "The code cannot be changed." : undefined}
          >
            <Input
              value={code}
              disabled={!!branch}
              onChange={(e) => setCode(e.target.value)}
            />
          </Labeled>
          <Labeled label="Name" error={errors.name}>
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </Labeled>
          <Labeled label="Address">
            <Input value={address} onChange={(e) => setAddress(e.target.value)} />
          </Labeled>
          <ErrorMsg error={m.error} />
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
              {m.isPending ? "Saving…" : "Save"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function Tills({
  sessionId,
  bankId,
  branchId,
  readOnly,
}: {
  sessionId: string;
  bankId: string;
  branchId: string;
  readOnly: boolean;
}) {
  const tills = useTills(sessionId, bankId, branchId);
  const create = useCreateTill(sessionId, bankId, branchId);
  const [code, setCode] = useState("");
  const [err, setErr] = useState<string | null>(null);

  function submit(ev: React.FormEvent) {
    ev.preventDefault();
    if (!code.trim()) {
      setErr("Enter a till code");
      return;
    }
    setErr(null);
    create.mutate(
      { code: code.trim() },
      {
        onSuccess: () => {
          toast.success("Till created");
          setCode("");
        },
      },
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-xs font-medium tracking-wide text-text-muted uppercase">
        Tills
      </p>
      <QueryState query={tills}>
        {tills.data?.length ? (
          <ul className="flex flex-wrap gap-2">
            {tills.data.map((t) => (
              <li
                key={t.id}
                className="rounded-md bg-hover px-2.5 py-1 font-mono text-xs text-text-strong"
              >
                {t.code}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-text-muted">No tills yet.</p>
        )}
      </QueryState>
      {!readOnly && (
        <form onSubmit={submit} noValidate className="flex flex-wrap items-start gap-2">
          <div className="w-40">
            <Input
              aria-label="Till code"
              placeholder="Till code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
            />
            {err && <p className="mt-1 text-sm text-fin-danger">{err}</p>}
          </div>
          <Button type="submit" variant="outline" disabled={create.isPending}>
            <Plus /> {create.isPending ? "Adding…" : "Add till"}
          </Button>
        </form>
      )}
      <ErrorMsg error={create.error} />
    </div>
  );
}

function BankBranches({
  session,
  bank,
  readOnly,
}: {
  session: SessionOut;
  bank: BankOut;
  readOnly: boolean;
}) {
  const branches = useBranches(session.id, bank.id);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<BranchOut | null>(null);

  return (
    <section className="overflow-hidden rounded-xl border border-border bg-card shadow-xs">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-text-strong">
          <Building2 className="size-4 text-bank-primary" /> {bank.name}
        </h2>
        {!readOnly && (
          <Button size="sm" onClick={() => setCreating(true)}>
            <Plus /> Create branch
          </Button>
        )}
      </div>
      <div className="space-y-4 p-5">
        <QueryState query={branches}>
          {branches.data?.length ? (
            branches.data.map((b) => (
              <div key={b.id} className="space-y-4 rounded-lg border border-border p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium text-text-strong">
                      {b.name}{" "}
                      <span className="font-mono text-xs font-normal text-text-muted">
                        {b.code}
                      </span>
                    </p>
                    <p className="text-sm text-text-muted">
                      {b.address || "No address"}
                    </p>
                  </div>
                  {!readOnly && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setEditing(b)}
                    >
                      <Pencil /> Edit
                    </Button>
                  )}
                </div>
                <Tills
                  sessionId={session.id}
                  bankId={bank.id}
                  branchId={b.id}
                  readOnly={readOnly}
                />
              </div>
            ))
          ) : (
            <EmptyState
              title="No branches yet"
              description="Create a branch to give this bank a vault and tills."
            />
          )}
        </QueryState>
      </div>
      {creating && (
        <BranchDialog
          sessionId={session.id}
          bankId={bank.id}
          open
          onOpenChange={(o) => !o && setCreating(false)}
        />
      )}
      {editing && (
        <BranchDialog
          key={editing.id}
          sessionId={session.id}
          bankId={bank.id}
          branch={editing}
          open
          onOpenChange={(o) => !o && setEditing(null)}
        />
      )}
    </section>
  );
}

export function BranchesTab({
  session,
  readOnly,
}: {
  session: SessionOut;
  readOnly: boolean;
}) {
  const banks = useBanks(session.id);
  return (
    <div className="space-y-4">
      <p className="max-w-xl text-sm text-text-muted">
        Each branch has one vault and any number of tills. Branch codes cannot
        be changed after creation.
      </p>
      <QueryState query={banks}>
        {banks.data?.length ? (
          banks.data.map((b) => (
            <BankBranches key={b.id} session={session} bank={b} readOnly={readOnly} />
          ))
        ) : (
          <EmptyState
            title="No banks yet"
            description="Banks are created when the session is opened."
          />
        )}
      </QueryState>
    </div>
  );
}
