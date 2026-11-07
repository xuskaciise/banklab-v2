import { cn } from "@/lib/utils";

export function Field({
  id,
  label,
  error,
  className,
  ...props
}: React.ComponentProps<"input"> & {
  id: string;
  label: string;
  error?: string;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="text-sm font-medium text-text-strong">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
        className={cn(
          "h-10 w-full rounded-md border border-border bg-card px-3 text-sm text-text-body outline-none focus-visible:ring-2 focus-visible:ring-bank-accent aria-invalid:border-fin-danger",
          className,
        )}
        {...props}
      />
      {error && (
        <p id={`${id}-error`} className="text-sm text-fin-danger">
          {error}
        </p>
      )}
    </div>
  );
}

export function FormError({ message }: { message?: string | null }) {
  if (!message) return null;
  return (
    <p
      role="alert"
      className="rounded-md bg-fin-danger-bg px-3 py-2 text-sm text-fin-danger"
    >
      {message}
    </p>
  );
}
