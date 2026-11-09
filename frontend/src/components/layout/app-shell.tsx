"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { KeyRound, LogOut, Menu } from "lucide-react";
import { isStudent, useLogout, useMe } from "@/lib/auth";
import { roleLabel, useSessionMe } from "@/lib/lab";
import { Button } from "@/components/ui/button";
import { Dialog, SheetContent } from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Breadcrumbs } from "@/components/layout/breadcrumbs";
import {
  SidebarContent,
  initials,
  roleName,
} from "@/components/layout/sidebar";
import { cn } from "@/lib/utils";

const STORAGE_KEY = "banklab.sidebar.collapsed";

function StudentContext({ sessionId }: { sessionId: string }) {
  const { data } = useSessionMe(sessionId);
  if (!data) return null;
  return (
    <div className="hidden items-center gap-3 text-xs text-text-muted lg:flex">
      {data.bank_name && (
        <span>
          Bank <span className="font-medium text-text-strong">{data.bank_name}</span>
        </span>
      )}
      <span>
        Business date{" "}
        <span className="font-medium text-text-strong tabular-nums">
          {data.business_date ?? "—"}
        </span>
      </span>
      <span className="rounded-full bg-bank-sky-light px-2 py-0.5 font-medium text-bank-primary">
        {roleLabel(data.role)}
      </span>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { data: user } = useMe();
  const logout = useLogout();
  const [collapsed, setCollapsed] = useState(false);
  const [drawer, setDrawer] = useState(false);

  useEffect(() => {
    try {
      // Restoring a persisted preference after hydration.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setCollapsed(localStorage.getItem(STORAGE_KEY) === "1");
    } catch {
      /* storage unavailable: keep default */
    }
  }, []);

  function toggle() {
    setCollapsed((c) => {
      const next = !c;
      try {
        localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
      } catch {
        /* ignore */
      }
      return next;
    });
  }

  // Full-bleed one-screen pages manage their own padding and height.
  const wide =
    pathname.startsWith("/s/") &&
    (pathname.endsWith("/teller/transactions") ||
      pathname.endsWith("/vault") ||
      pathname.split("/").filter(Boolean).length === 2);

  const studentSession = isStudent(user)
    ? pathname.match(/^\/s\/([^/]+)/)?.[1]
    : undefined;

  return (
    <div className="flex min-h-screen">
      <aside
        className={cn(
          "sticky top-0 hidden h-screen shrink-0 bg-sidebar text-sidebar-foreground transition-[width] duration-200 md:block",
          collapsed ? "w-[68px]" : "w-64",
        )}
      >
        <SidebarContent user={user} collapsed={collapsed} onToggle={toggle} />
      </aside>

      <Dialog open={drawer} onOpenChange={setDrawer}>
        <SheetContent aria-label="Navigation">
          <SidebarContent user={user} onNavigate={() => setDrawer(false)} />
        </SheetContent>
      </Dialog>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-card/90 px-4 backdrop-blur sm:px-6">
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            aria-label="Open navigation"
            onClick={() => setDrawer(true)}
          >
            <Menu />
          </Button>
          <Breadcrumbs className="flex-1" />
          {studentSession && <StudentContext sessionId={studentSession} />}
          {user && (
            <DropdownMenu>
              <DropdownMenuTrigger
                aria-label="Account menu"
                className="flex items-center gap-2 rounded-lg py-1 pr-2 pl-1 transition-colors hover:bg-hover"
              >
                <span className="flex size-8 items-center justify-center rounded-full bg-bank-navy text-xs font-semibold text-white">
                  {initials(user.full_name)}
                </span>
                <span className="hidden text-left leading-tight sm:block">
                  <span className="block max-w-40 truncate text-sm font-medium text-text-strong">
                    {user.full_name}
                  </span>
                  <span className="block text-xs text-text-muted">
                    {roleName(user.platform_role)}
                  </span>
                </span>
              </DropdownMenuTrigger>
              <DropdownMenuContent className="w-64">
                <div className="px-2.5 py-2">
                  <p className="truncate text-sm font-semibold text-text-strong">
                    {user.full_name}
                  </p>
                  <p className="truncate text-xs text-text-muted">{user.username}</p>
                  <span className="mt-1.5 inline-flex rounded-full bg-bank-sky-light px-2 py-0.5 text-xs font-medium text-bank-primary">
                    {roleName(user.platform_role)}
                  </span>
                </div>
                <DropdownMenuSeparator />
                <DropdownMenuItem render={<Link href="/change-password" />}>
                  <KeyRound /> Change password
                </DropdownMenuItem>
                <DropdownMenuItem
                  destructive
                  disabled={logout.isPending}
                  onClick={() =>
                    logout.mutate(undefined, {
                      onSettled: () =>
                        router.replace(
                          user && !isStudent(user) ? "/staff/login" : "/login",
                        ),
                    })
                  }
                >
                  <LogOut /> Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </header>
        <main
          className={cn(
            "min-w-0 flex-1",
            wide
              ? "w-full"
              : "mx-auto w-full max-w-7xl p-4 sm:p-6 lg:p-8",
          )}
        >
          {children}
        </main>
      </div>
    </div>
  );
}
