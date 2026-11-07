"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ChevronsLeft,
  ChevronsRight,
  GraduationCap,
  LayoutDashboard,
  Landmark,
  Layers,
} from "lucide-react";
import type { Me } from "@/lib/api/types";
import { isStudent } from "@/lib/auth";
import { useSessionMe } from "@/lib/lab";
import { Tooltip } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

type NavItem = {
  label: string;
  href: string;
  match: RegExp;
  icon: React.ComponentType<{ className?: string }>;
};

// Only pages that exist today. Add an entry when its page ships.
const STAFF_NAV: NavItem[] = [
  {
    label: "Overview",
    href: "/instructor",
    match: /^\/instructor$/,
    icon: LayoutDashboard,
  },
  {
    label: "Classes",
    href: "/instructor/classes",
    match: /^\/instructor\/(classes|sessions)/,
    icon: GraduationCap,
  },
];
const STUDENT_NAV: NavItem[] = [
  {
    label: "My sessions",
    href: "/sessions",
    match: /^\/(sessions|s\/[^/]+\/?$)/,
    icon: Layers,
  },
];

export function navFor(
  user: Me | null | undefined,
  session?: { id: string; permissions: string[] },
): NavItem[] {
  if (!isStudent(user)) return STAFF_NAV;
  const items = [...STUDENT_NAV];
  if (session?.permissions.includes("vault.view"))
    items.push({
      label: "Vault",
      href: `/s/${session.id}/vault`,
      match: /^\/s\/[^/]+\/vault/,
      icon: Landmark,
    });
  return items;
}

export function initials(name?: string | null) {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : ""))
    .toUpperCase();
}

export function roleName(role?: string | null) {
  return role ? role.charAt(0).toUpperCase() + role.slice(1) : "";
}

export function SidebarContent({
  user,
  collapsed = false,
  onToggle,
  onNavigate,
}: {
  user: Me | null | undefined;
  collapsed?: boolean;
  onToggle?: () => void;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  const sessionId = pathname.match(/^\/s\/([^/]+)/)?.[1];
  const sessionMe = useSessionMe(sessionId ?? "");
  const nav = navFor(
    user,
    sessionId && sessionMe.data
      ? {
          id: sessionId,
          permissions: sessionMe.data.permissions.map((p) => p.code),
        }
      : undefined,
  );
  return (
    <div className="flex h-full flex-col">
      <div
        className={cn(
          "flex h-14 shrink-0 items-center gap-3 border-b border-sidebar-border",
          collapsed ? "justify-center px-2" : "px-4",
        )}
      >
        <span className="flex size-9 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-white shadow-sm">
          <Image
            src="/logo.png"
            alt="SIU logo"
            width={36}
            height={36}
            className="size-9 object-contain"
            priority
          />
        </span>
        {!collapsed && (
          <div className="min-w-0 leading-tight">
            <p className="truncate text-sm font-semibold tracking-tight text-white">
              BankLab
            </p>
            <p className="truncate text-[11px] text-sidebar-foreground/60">
              Training bank
            </p>
          </div>
        )}
      </div>

      <nav aria-label="Main" className="flex-1 space-y-1 overflow-y-auto p-3">
        {!collapsed && (
          <p className="px-2 pb-1 text-[11px] font-medium tracking-wider text-sidebar-foreground/50 uppercase">
            Menu
          </p>
        )}
        {nav.map((item) => {
          const active = item.match.test(pathname);
          const Icon = item.icon;
          return (
            <Tooltip key={item.href} content={item.label} disabled={!collapsed}>
              <Link
                href={item.href}
                onClick={onNavigate}
                aria-current={active ? "page" : undefined}
                aria-label={collapsed ? item.label : undefined}
                className={cn(
                  "group relative flex h-9 items-center gap-3 rounded-md text-sm font-medium transition-colors",
                  collapsed ? "justify-center" : "px-3",
                  active
                    ? "bg-sidebar-accent text-white"
                    : "text-sidebar-foreground/75 hover:bg-sidebar-accent hover:text-white",
                )}
              >
                {active && (
                  <span
                    aria-hidden="true"
                    className="absolute top-1.5 bottom-1.5 -left-3 w-1 rounded-r bg-sidebar-primary"
                  />
                )}
                <Icon
                  className={cn(
                    "size-[18px] shrink-0",
                    active ? "text-sidebar-primary" : "text-sidebar-foreground/60",
                  )}
                />
                {!collapsed && <span className="truncate">{item.label}</span>}
              </Link>
            </Tooltip>
          );
        })}
      </nav>

      <div className="shrink-0 border-t border-sidebar-border p-3">
        {user && (
          <div
            className={cn(
              "flex items-center gap-3 rounded-md",
              collapsed ? "justify-center" : "px-1 py-1",
            )}
          >
            <Tooltip
              content={`${user.full_name} (${roleName(user.platform_role)})`}
              disabled={!collapsed}
            >
              <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-sidebar-accent text-xs font-semibold text-white ring-1 ring-sidebar-border">
                {initials(user.full_name)}
              </span>
            </Tooltip>
            {!collapsed && (
              <div className="min-w-0 leading-tight">
                <p className="truncate text-sm font-medium text-white">
                  {user.full_name}
                </p>
                <p className="truncate text-xs text-sidebar-foreground/60">
                  {roleName(user.platform_role)}
                </p>
              </div>
            )}
          </div>
        )}
        {onToggle && (
          <button
            type="button"
            onClick={onToggle}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className={cn(
              "mt-2 flex h-8 w-full items-center gap-2 rounded-md text-xs text-sidebar-foreground/60 transition-colors hover:bg-sidebar-accent hover:text-white",
              collapsed ? "justify-center" : "px-3",
            )}
          >
            {collapsed ? (
              <ChevronsRight className="size-4" />
            ) : (
              <>
                <ChevronsLeft className="size-4" /> Collapse
              </>
            )}
          </button>
        )}
      </div>
    </div>
  );
}
