import { cn } from "@/lib/utils";

export function Checkbox({
  className,
  ...props
}: Omit<React.ComponentProps<"input">, "type">) {
  return (
    <input
      type="checkbox"
      className={cn(
        "size-4 cursor-pointer rounded border-border accent-bank-primary",
        className,
      )}
      {...props}
    />
  );
}
