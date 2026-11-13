import * as React from "react";
import { cn } from "@/lib/utils";

export const controlCls =
  "h-11 w-full rounded-lg border border-border bg-card px-3.5 text-base text-text-strong outline-none transition-colors placeholder:text-text-muted hover:border-text-muted focus-visible:border-bank-accent focus-visible:ring-2 focus-visible:ring-bank-accent/40 disabled:cursor-not-allowed disabled:bg-surface disabled:opacity-60 aria-invalid:border-fin-danger aria-invalid:ring-fin-danger/20 sm:text-sm";

const CHEVRON =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%2364748b' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E\")";

export function Input({ className, ...props }: React.ComponentProps<"input">) {
  return <input className={cn(controlCls, className)} {...props} />;
}

export function Select({
  className,
  style,
  ...props
}: React.ComponentProps<"select">) {
  return (
    <select
      className={cn(controlCls, "appearance-none bg-no-repeat pr-9", className)}
      style={{
        backgroundImage: CHEVRON,
        backgroundPosition: "right 0.6rem center",
        ...style,
      }}
      {...props}
    />
  );
}

export function Textarea({
  className,
  ...props
}: React.ComponentProps<"textarea">) {
  return (
    <textarea
      className={cn(controlCls, "h-auto min-h-[90px] resize-y py-2.5 leading-relaxed", className)}
      {...props}
    />
  );
}
