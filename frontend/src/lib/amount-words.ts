// Exact port of backend/apps/banking/receipt_text.py::amount_in_words.
const ONES = (
  "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen " +
  "fifteen sixteen seventeen eighteen nineteen"
).split(" ");
const TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split(" ");
const SCALES: [bigint, string][] = [
  [BigInt(10) ** BigInt(12), "trillion"],
  [BigInt(10) ** BigInt(9), "billion"],
  [BigInt(10) ** BigInt(6), "million"],
  [BigInt(1000), "thousand"],
];
const CURRENCY_NAME: Record<string, string> = { USD: "US Dollars", SOS: "Somali Shillings" };

const ZERO = BigInt(0);
const HUNDRED = BigInt(100);
const TEN = BigInt(10);

/** Returns null when the number is outside what the word table can express (Python raises). */
function below1000(n: bigint): string | null {
  const parts: string[] = [];
  if (n >= HUNDRED) {
    const h = ONES[Number(n / HUNDRED)];
    if (h === undefined) return null;
    parts.push(`${h} hundred`);
    n %= HUNDRED;
  }
  if (n >= BigInt(20)) {
    const ones = Number(n % TEN);
    parts.push(TENS[Number(n / TEN)] + (ones ? `-${ONES[ones]}` : ""));
  } else if (n > ZERO || parts.length === 0) {
    parts.push(ONES[Number(n)]);
  }
  return parts.join(" ");
}

function numberToWords(n: bigint): string | null {
  if (n < BigInt(1000)) return below1000(n);
  const parts: string[] = [];
  for (const [size, name] of SCALES) {
    if (n >= size) {
      // numberToWords, not below1000: n / 10^12 can exceed 999 (16-digit amounts).
      const w = numberToWords(n / size);
      if (w === null) return null;
      parts.push(`${w} ${name}`);
      n %= size;
    }
  }
  if (n > ZERO) {
    const w = below1000(n);
    if (w === null) return null;
    parts.push(w);
  }
  return parts.join(" ");
}

/** Decimal string -> integer cents (half-up at the 3rd decimal), no float math. */
function toCents(value: string): bigint | null {
  const m = /^[+-]?(\d*)(?:\.(\d*))?$/.exec(value.replace(/,/g, "").trim());
  if (!m || (!m[1] && !m[2])) return null;
  const whole = m[1] || "0";
  const frac = (m[2] ?? "").padEnd(3, "0");
  let cents = BigInt(whole + frac.slice(0, 2));
  if (frac[2] >= "5") cents += BigInt(1);
  return cents;
}

export function amountInWords(value: string, currency: string): string | null {
  if (!value || !currency) return null;
  const total = toCents(value);
  if (total === null) return null;
  const whole = total / HUNDRED;
  const cents = Number(total % HUNDRED);
  const words = numberToWords(whole);
  if (words === null) return null;
  const cap = words.charAt(0).toUpperCase() + words.slice(1);
  return `${cap} ${CURRENCY_NAME[currency] ?? currency} and ${String(cents).padStart(2, "0")}/100`;
}
