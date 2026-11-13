"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight } from "lucide-react";
import { useClass, useSession, useSessionMe } from "@/lib/lab";
import { cn } from "@/lib/utils";

type Crumb = { label: React.ReactNode; href?: string };

function ClassName({ id }: { id: string }) {
  const { data } = useClass(id);
  return <>{data?.name ?? "Class"}</>;
}
function SessionName({ id }: { id: string }) {
  const { data } = useSession(id);
  return <>{data?.name ?? "Session"}</>;
}
function SessionClassName({ id }: { id: string }) {
  const { data } = useSession(id);
  return <>{data?.class_name ?? "Class"}</>;
}
function StudentSessionName({ id }: { id: string }) {
  const { data } = useSessionMe(id);
  return <>{data?.session_name ?? "Session"}</>;
}
/** Class link for a session crumb needs the class id, so it is its own component. */
function SessionClassCrumb({ id }: { id: string }) {
  const { data } = useSession(id);
  const label = <SessionClassName id={id} />;
  return data ? (
    <Link
      href={`/instructor/classes/${data.class_id}`}
      className="truncate rounded hover:text-text-strong"
    >
      {label}
    </Link>
  ) : (
    <span>{label}</span>
  );
}

function crumbsFor(pathname: string): Crumb[] {
  let m: RegExpMatchArray | null;
  if (pathname === "/instructor") return [{ label: "Overview" }];
  if (pathname === "/instructor/classes") return [{ label: "Classes" }];
  if ((m = pathname.match(/^\/instructor\/classes\/([^/]+)\/import$/)))
    return [
      { label: "Classes", href: "/instructor/classes" },
      { label: <ClassName id={m[1]} />, href: `/instructor/classes/${m[1]}` },
      { label: "Import students" },
    ];
  if ((m = pathname.match(/^\/instructor\/classes\/([^/]+)$/)))
    return [
      { label: "Classes", href: "/instructor/classes" },
      { label: <ClassName id={m[1]} /> },
    ];
  if (pathname === "/instructor/sessions/new")
    return [
      { label: "Classes", href: "/instructor/classes" },
      { label: "New session" },
    ];
  if ((m = pathname.match(/^\/instructor\/sessions\/([^/]+)$/)))
    return [
      { label: "Classes", href: "/instructor/classes" },
      { label: <SessionClassCrumb id={m[1]} /> },
      { label: <SessionName id={m[1]} /> },
    ];
  if ((m = pathname.match(/^\/instructor\/exams\/([^/]+)(\/results)?$/)))
    return [
      { label: "Classes", href: "/instructor/classes" },
      { label: <SessionClassCrumb id={m[1]} /> },
      { label: <SessionName id={m[1]} />, href: `/instructor/sessions/${m[1]}` },
      m[2]
        ? { label: "Exam", href: `/instructor/exams/${m[1]}` }
        : { label: "Exam setup" },
      ...(m[2] ? [{ label: "Results" }] : []),
    ];
  if (pathname === "/sessions") return [{ label: "My sessions" }];
  if ((m = pathname.match(/^\/s\/([^/]+)/)))
    return [
      { label: "My sessions", href: "/sessions" },
      { label: <StudentSessionName id={m[1]} /> },
    ];
  if (pathname === "/change-password")
    return [{ label: "Account" }, { label: "Change password" }];
  return [];
}

export function Breadcrumbs({ className }: { className?: string }) {
  const pathname = usePathname();
  const crumbs = crumbsFor(pathname);
  if (!crumbs.length) return null;
  return (
    <nav aria-label="Breadcrumb" className={cn("min-w-0", className)}>
      <ol className="flex min-w-0 items-center gap-1.5 text-sm text-text-muted">
        {crumbs.map((c, i) => {
          const last = i === crumbs.length - 1;
          return (
            <li
              key={i}
              className={cn("flex min-w-0 items-center gap-1.5", !last && "max-sm:hidden")}
            >
              {i > 0 && <ChevronRight className="size-3.5 shrink-0 max-sm:hidden" />}
              {c.href && !last ? (
                <Link href={c.href} className="truncate rounded hover:text-text-strong">
                  {c.label}
                </Link>
              ) : (
                <span
                  aria-current={last ? "page" : undefined}
                  className={cn("truncate", last && "font-medium text-text-strong")}
                >
                  {c.label}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
