"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Briefcase, GraduationCap } from "lucide-react";
import { cn } from "@/lib/utils";

const ROLES = [
  { href: "/login", label: "Student", icon: GraduationCap },
  { href: "/staff/login", label: "Instructor / Staff", icon: Briefcase },
] as const;

/** Segmented switch between the student and staff sign-in pages. */
export function LoginRoleSwitch() {
  const path = usePathname();
  return (
    <nav
      aria-label="Sign in as"
      className="mb-4 grid grid-cols-2 gap-1 rounded-xl bg-muted p-1 ring-1 ring-border"
    >
      {ROLES.map(({ href, label, icon: Icon }) => {
        const active = path === href;
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
              active
                ? "bg-card text-bank-primary shadow-sm ring-1 ring-border"
                : "text-text-muted hover:bg-card/60 hover:text-text-strong",
            )}
          >
            <Icon className="size-4" aria-hidden="true" />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
