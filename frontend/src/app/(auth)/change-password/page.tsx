"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { isStudent, useChangePassword, useMe } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FormError } from "@/components/auth/field";

export default function ChangePasswordPage() {
  const router = useRouter();
  const change = useChangePassword();
  // AuthGate redirects students away; this is only a render guard.
  const { data: me } = useMe();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState<{
    current?: string;
    next?: string;
    confirm?: string;
  }>({});

  function onSubmit(ev: React.FormEvent) {
    ev.preventDefault();
    const e = {
      current: current ? undefined : "Enter your current password",
      next: next.length >= 6 ? undefined : "Use at least 6 characters",
      confirm: confirm === next ? undefined : "Passwords do not match",
    };
    setErrors(e);
    if (e.current || e.next || e.confirm) return;
    change.mutate(
      { current_password: current, new_password: next },
      { onSuccess: () => router.replace("/") },
    );
  }

  if (isStudent(me)) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-text-strong">Change password</CardTitle>
        <p className="text-sm text-text-muted">
          First login: choose a new password.
        </p>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} noValidate className="space-y-4">
          <Field
            id="current"
            label="Current password"
            type="password"
            autoComplete="current-password"
            autoFocus
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            error={errors.current}
          />
          <Field
            id="new"
            label="New password"
            type="password"
            autoComplete="new-password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
            error={errors.next}
          />
          <Field
            id="confirm"
            label="Confirm new password"
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            error={errors.confirm}
          />
          <FormError message={change.isError ? change.error.message : null} />
          <Button type="submit" className="w-full" disabled={change.isPending}>
            {change.isPending ? "Saving…" : "Change password"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
