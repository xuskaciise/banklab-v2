/** Page-scoped control styles for the transaction form (shared ui defaults stay untouched). */
export const FIELD =
  "h-11 rounded-lg px-3.5 text-base sm:text-sm shadow-none hover:border-text-muted focus-visible:ring-bank-accent/40 disabled:bg-surface";

export const AREA =
  "min-h-[90px] resize-y rounded-lg px-3.5 py-2.5 text-base sm:text-sm shadow-none hover:border-text-muted focus-visible:ring-bank-accent/40 disabled:bg-surface";

const BTN =
  "h-11 rounded-lg px-5 text-sm transition-colors focus-visible:ring-2 focus-visible:ring-bank-accent focus-visible:ring-offset-2";

export const BTN_PRIMARY = `${BTN} bg-bank-primary font-semibold text-white hover:bg-bank-navy active:bg-bank-navy disabled:opacity-50`;
export const BTN_SECONDARY = `${BTN} border border-border bg-card font-medium text-text-body hover:bg-hover active:bg-hover disabled:opacity-50`;
export const BTN_FIND = `${BTN} shrink-0 border border-border bg-surface px-4 font-medium text-text-strong hover:bg-bank-sky-light hover:border-bank-accent active:bg-bank-sky-light disabled:opacity-60`;
