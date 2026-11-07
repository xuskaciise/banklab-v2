"use client";

import Link from "next/link";
import { ChevronDown } from "lucide-react";
import type { ClassOut } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

/** Button that lists the instructor's classes; each item links to hrefFor(class). */
export function ClassPickerMenu({
  label,
  icon,
  classes,
  hrefFor,
  variant = "outline",
}: {
  label: string;
  icon: React.ReactNode;
  classes: ClassOut[] | undefined;
  hrefFor: (c: ClassOut) => string;
  variant?: "outline" | "default";
}) {
  const none = !classes?.length;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        disabled={none}
        render={
          <Button variant={variant} className="w-full justify-between">
            <span className="flex items-center gap-2">
              {icon} {label}
            </span>
            <ChevronDown className="opacity-60" />
          </Button>
        }
      />
      <DropdownMenuContent align="start" className="w-64">
        <DropdownMenuLabel>Choose a class</DropdownMenuLabel>
        {classes?.map((c) => (
          <DropdownMenuItem key={c.id} render={<Link href={hrefFor(c)} />}>
            <span className="truncate">{c.name}</span>
            <span className="ml-auto font-mono text-xs text-text-muted">
              {c.code}
            </span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
