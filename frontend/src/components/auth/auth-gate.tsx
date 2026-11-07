"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { isStudent, useMe } from "@/lib/auth";
import type { Me } from "@/lib/api/types";

const AUTH_PAGES = ["/login", "/staff/login"];

function loginPathFor(pathname: string) {
  const staffOnly = /^\/(instructor|admin)(\/|$)/.test(pathname);
  return staffOnly ? "/staff/login" : "/login";
}

function redirectFor(
  pathname: string,
  user: Me | null | undefined,
): string | null {
  if (!user) {
    return AUTH_PAGES.includes(pathname) ? null : loginPathFor(pathname);
  }
  // Students have no password, so they are never sent to /change-password.
  if (isStudent(user)) {
    return AUTH_PAGES.includes(pathname) || pathname === "/change-password"
      ? "/"
      : null;
  }
  if (user.must_change_password) {
    return pathname === "/change-password" ? null : "/change-password";
  }
  return AUTH_PAGES.includes(pathname) ? "/" : null;
}

function GateSkeleton() {
  return (
    <div
      role="status"
      aria-label="Loading"
      className="flex min-h-screen items-center justify-center bg-surface"
    >
      <div className="h-24 w-72 animate-pulse rounded-lg bg-border" />
    </div>
  );
}

/**
 * Redirects based on auth state and renders children only when the current
 * route is allowed for the current user. Enforcement is on the API.
 */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { data: user, isPending, isError } = useMe();
  const redirectTo = isPending || isError ? null : redirectFor(pathname, user);

  useEffect(() => {
    if (redirectTo) router.replace(redirectTo);
  }, [redirectTo, router]);

  if (isPending) return <GateSkeleton />;
  if (isError) {
    return (
      <div
        role="alert"
        className="flex min-h-screen items-center justify-center bg-surface p-6 text-sm text-fin-danger"
      >
        Cannot reach the server. Please try again later.
      </div>
    );
  }
  if (redirectTo) return <GateSkeleton />;
  return <>{children}</>;
}
