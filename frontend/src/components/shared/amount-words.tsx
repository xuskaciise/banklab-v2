import { amountInWords } from "@/lib/amount-words";
import { cn } from "@/lib/utils";

/** Muted italic amount-in-words line. `text` (server value) wins over the live helper. */
export function AmountWords({
  value,
  currency,
  text,
  className,
}: {
  value?: string;
  currency?: string;
  text?: string | null;
  className?: string;
}) {
  const words = text ?? (value && currency ? amountInWords(value, currency) : null);
  return (
    <p
      aria-live="polite"
      className={cn("text-xs text-text-muted italic", !words && "hidden", className)}
    >
      {words}
    </p>
  );
}
