"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { loginErrorMessage, useStudentLogin } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FormError } from "@/components/auth/field";

export default function StudentLoginPage() {
  const router = useRouter();
  const login = useStudentLogin();
  const [studentId, setStudentId] = useState("");
  const [phone, setPhone] = useState("");
  const [errors, setErrors] = useState<{ studentId?: string; phone?: string }>(
    {},
  );

  function onSubmit(ev: React.FormEvent) {
    ev.preventDefault();
    const next = {
      studentId: studentId.trim() ? undefined : "Enter your Student ID",
      phone: phone.trim() ? undefined : "Enter your phone number",
    };
    setErrors(next);
    if (next.studentId || next.phone) return;
    login.mutate(
      { student_id: studentId.trim(), phone: phone.trim() },
      { onSuccess: () => router.replace("/") },
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-text-strong">Sign in</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} noValidate className="space-y-4">
          <Field
            id="student-id"
            label="Student ID"
            autoComplete="username"
            autoFocus
            value={studentId}
            onChange={(e) => setStudentId(e.target.value)}
            error={errors.studentId}
          />
          <Field
            id="phone"
            label="Phone number"
            type="tel"
            autoComplete="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            error={errors.phone}
          />
          <FormError
            message={login.isError ? loginErrorMessage(login.error) : null}
          />
          <Button type="submit" className="w-full" disabled={login.isPending}>
            {login.isPending ? "Signing in…" : "Sign in"}
          </Button>
        </form>
        <p className="mt-4 text-center text-xs text-text-muted">
          <Link href="/staff/login" className="underline hover:text-text-strong">
            Staff login
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}
