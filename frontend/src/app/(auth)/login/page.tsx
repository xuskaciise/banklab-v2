"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError } from "@/lib/api/client";
import { useLogin } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FormError } from "@/components/auth/field";

function errorMessage(e: unknown) {
  if (e instanceof ApiError && e.status === 429) {
    return "Too many attempts, try again in a few minutes";
  }
  return e instanceof Error ? e.message : "Login failed";
}

export default function LoginPage() {
  const router = useRouter();
  const login = useLogin();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<{ username?: string; password?: string }>(
    {},
  );

  function onSubmit(ev: React.FormEvent) {
    ev.preventDefault();
    const next = {
      username: username.trim() ? undefined : "Enter your ID",
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
        <CardTitle className="text-text-strong">Sign in</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} noValidate className="space-y-4">
          <Field
            id="username"
            label="Student / Staff ID"
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
          <FormError message={login.isError ? errorMessage(login.error) : null} />
          <Button type="submit" className="w-full" disabled={login.isPending}>
            {login.isPending ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
