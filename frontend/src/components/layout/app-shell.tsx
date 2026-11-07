"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { isStudent, useLogout, useMe } from "@/lib/auth";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const NAV_ITEMS = ["Dashboard", "Customers", "Accounts", "Teller", "Reports"];

const CONTEXT_ITEMS = [
  { label: "Session", value: "—" },
  { label: "Business date", value: "—" },
  { label: "Role", value: "—" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { data: user } = useMe();
  const logout = useLogout();
  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 flex h-screen w-60 shrink-0 flex-col bg-sidebar text-sidebar-foreground">
        <div className="px-6 py-5 text-xl font-semibold tracking-tight text-white">
          BankLab
        </div>
        <nav aria-label="Main" className="flex flex-col gap-1 px-3">
          {NAV_ITEMS.map((label) => (
            <Link
              key={label}
              href="#"
              className="rounded-md px-3 py-2 text-sm font-medium text-sidebar-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
            >
              {label}
            </Link>
          ))}
        </nav>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center gap-6 border-b border-border bg-card px-6 text-sm">
          {CONTEXT_ITEMS.map(({ label, value }) => (
            <span key={label} className="text-text-muted">
              {label}:{" "}
              <span className="font-medium text-text-strong">{value}</span>
            </span>
          ))}
          <div className="ml-auto flex items-center gap-3">
            {user && (
              <>
                <span className="font-medium text-text-strong">
                  {user.full_name}
                </span>
                <Badge variant="secondary" className="capitalize">
                  {user.platform_role}
                </Badge>
              </>
            )}
            {user && !isStudent(user) && (
              <Link
                href="/change-password"
                className="text-text-muted underline hover:text-text-strong"
              >
                Change password
              </Link>
            )}
            <Button
              variant="outline"
              size="sm"
              disabled={logout.isPending}
              onClick={() =>
                logout.mutate(undefined, {
                  onSettled: () =>
                    router.replace(user && !isStudent(user) ? "/staff/login" : "/login"),
                })
              }
            >
              Log out
            </Button>
          </div>
        </header>
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
