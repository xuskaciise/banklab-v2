"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { loginErrorMessage, useStaffLogin } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FormError } from "@/components/auth/field";

export default function StaffLoginPage() {
  const router = useRouter();
  const login = useStaffLogin();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<{ username?: string; password?: string }>(
    {},
  );

  function onSubmit(ev: React.FormEvent) {
    ev.preventDefault();
    const next = {
      username: username.trim() ? undefined : "Enter your username",
      password: password ? undefined : "Enter your password",
    };
    setErrors(next);
    if (next.username || next.password) return;
    login.mutate(
      { username: username.trim(), password },
      {
        onSuccess: (data) =>
          router.replace(
            data.user.must_change_password ? "/change-password" : "/",
          ),
      },
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-text-strong">Staff sign in</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} noValidate className="space-y-4">
          <Field
            id="username"
            label="Username"
            autoComplete="username"
            autoFocus
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            error={errors.username}
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
          <Link href="/login" className="underline hover:text-text-strong">
            Student login
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}
