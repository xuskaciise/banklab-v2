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
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<{ studentId?: string; password?: string }>(
    {},
  );

  function onSubmit(ev: React.FormEvent) {
    ev.preventDefault();
    const next = {
      studentId: studentId.trim() ? undefined : "Enter your Student ID",
      password: password ? undefined : "Enter your password",
    };
    setErrors(next);
    if (next.studentId || next.password) return;
    login.mutate(
      { student_id: studentId.trim(), password },
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
            id="password"
            label="Password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={errors.password}
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
