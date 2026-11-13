"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { loginErrorMessage, useStudentLogin } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FormError } from "@/components/auth/field";
import { LoginRoleSwitch } from "@/components/auth/login-role-switch";

export default function StudentLoginPage() {
  const router = useRouter();
  const login = useStudentLogin();
  const [studentId, setStudentId] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<{
    studentId?: string;
    password?: string;
  }>({});

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
    <>
      <LoginRoleSwitch />
      <Card className="shadow-md [--card-spacing:--spacing(6)]">
        <CardHeader>
          <CardTitle className="text-xl font-semibold tracking-tight text-text-strong">
            Student sign in
          </CardTitle>
          <p className="text-sm text-text-muted">
            Use your Student ID and password.
          </p>
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
        </CardContent>
      </Card>
    </>
  );
}
