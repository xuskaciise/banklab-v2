"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { isStudent, useLogout, useMe } from "@/lib/auth";
import { roleLabel, useSession, useSessionMe } from "@/lib/lab";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type NavItem = { label: string; href: string; match: RegExp };

const INSTRUCTOR_NAV: NavItem[] = [
  { label: "Dashboard", href: "/instructor", match: /^\/instructor$/ },
  {
    label: "Classes",
    href: "/instructor/classes",
    match: /^\/instructor\/(classes|sessions)/,
  },
];
const STUDENT_NAV: NavItem[] = [
  { label: "My sessions", href: "/sessions", match: /^\/(sessions|s\/)/ },
];

function Sep() {
  return <span className="text-text-muted">›</span>;
}

function StudentContext({ sessionId }: { sessionId: string }) {
  const { data } = useSessionMe(sessionId);
  if (!data) return <span className="text-text-muted">Loading session…</span>;
  return (
    <>
      <span className="flex items-center gap-2 text-text-muted">
        {data.class_name} <Sep />
        <span className="font-medium text-text-strong">{data.session_name}</span>
        {data.bank_name && (
          <>
            <Sep /> <span className="text-text-strong">{data.bank_name}</span>
          </>
        )}
      </span>
      <span className="text-text-muted">
        Business date:{" "}
        <span className="font-medium text-text-strong">
          {data.business_date ?? "—"}
        </span>
      </span>
      <Badge className="bg-bank-sky-light text-bank-primary">
        {roleLabel(data.role)}
      </Badge>
    </>
  );
}

function InstructorSessionContext({ sessionId }: { sessionId: string }) {
  const { data } = useSession(sessionId);
  if (!data) return null;
  return (
    <span className="flex items-center gap-2 text-text-muted">
      {data.class_name} <Sep />
      <span className="font-medium text-text-strong">{data.name}</span>
    </span>
  );
}

function ContextBar({ student }: { student: boolean }) {
  const pathname = usePathname();
  const studentSession = pathname.match(/^\/s\/([^/]+)/)?.[1];
  const staffSession = pathname.match(/^\/instructor\/sessions\/([^/]+)/)?.[1];
  if (student && studentSession)
    return <StudentContext sessionId={studentSession} />;
  if (!student)
    return (
      <>
        {staffSession && staffSession !== "new" && (
          <InstructorSessionContext sessionId={staffSession} />
        )}
        <Badge className="bg-bank-sky-light text-bank-primary">
          Viewing as instructor
        </Badge>
      </>
    );
  return null;
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { data: user } = useMe();
  const logout = useLogout();
  const student = isStudent(user);
  const nav = student ? STUDENT_NAV : INSTRUCTOR_NAV;
  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 flex h-screen w-60 shrink-0 flex-col bg-sidebar text-sidebar-foreground">
        <div className="px-6 py-5 text-xl font-semibold tracking-tight text-white">
          BankLab
        </div>
        <nav aria-label="Main" className="flex flex-col gap-1 px-3">
          {nav.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              aria-current={item.match.test(pathname) ? "page" : undefined}
              className={cn(
                "rounded-md px-3 py-2 text-sm font-medium text-sidebar-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                item.match.test(pathname) &&
                  "bg-sidebar-accent text-sidebar-accent-foreground",
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex min-h-14 flex-wrap items-center gap-x-6 gap-y-2 border-b border-border bg-card px-6 py-2 text-sm">
          {user && <ContextBar student={student} />}
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
            {user && (
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
                    router.replace(
                      user && !isStudent(user) ? "/staff/login" : "/login",
                    ),
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
