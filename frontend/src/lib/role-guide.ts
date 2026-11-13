/** Plain-language descriptions of what a role can do, and the screens it uses. */

export type QuickAction = {
  href: (sid: string) => string;
  title: string;
  text: string;
  any: string[];
};

export const QUICK_ACTIONS: QuickAction[] = [
  {
    href: (sid) => `/s/${sid}/teller/transactions`,
    title: "New transaction",
    text: "Take a cash deposit or withdrawal, or move money between two accounts.",
    any: ["txn.cash_deposit", "txn.cash_withdrawal", "txn.transfer"],
  },
  {
    href: (sid) => `/s/${sid}/teller/till`,
    title: "My till",
    text: "Open your till for the day, see your cash and close it with a count.",
    any: ["till.open.request", "till.close"],
  },
  {
    href: (sid) => `/s/${sid}/approvals`,
    title: "Approvals",
    text: "Approve or reject transactions that are above a teller's limit.",
    any: ["approval.decide"],
  },
  {
    href: (sid) => `/s/${sid}/tills`,
    title: "Tills",
    text: "Approve tellers opening and closing their tills.",
    any: ["till.open.approve", "till.close.approve"],
  },
  {
    href: (sid) => `/s/${sid}/transactions`,
    title: "Transactions",
    text: "See the bank's transactions and print their receipts.",
    any: ["report.operational"],
  },
  {
    href: (sid) => `/s/${sid}/customers`,
    title: "Customers",
    text: "Find a customer and check their details and KYC.",
    any: ["customer.view"],
  },
  {
    href: (sid) => `/s/${sid}/accounts`,
    title: "Accounts",
    text: "Look up accounts and their balances.",
    any: ["account.view"],
  },
  {
    href: (sid) => `/s/${sid}/vault`,
    title: "Vault",
    text: "See the vault cash and approve cash moving to and from tellers.",
    any: ["vault.view"],
  },
];

/** One sentence per permission; codes not listed here are not shown. */
const ABILITY: Record<string, string> = {
  "customer.view": "View customer details",
  "customer.create": "Register new customers",
  "account.view": "Look up accounts and balances",
  "account.open": "Open new accounts",
  "account.statement": "Print account statements",
  "till.open.request": "Open your till at the start of the day",
  "till.close": "Close your till with a cash count",
  "till.open.approve": "Approve tellers opening their tills",
  "cash.vault_to_teller.request": "Ask the vault for more cash",
  "cash.teller_to_vault.request": "Send extra cash back to the vault",
  "cash.teller_to_teller.request": "Send cash to another teller",
  "cash.vault.approve_custodian": "Approve vault cash movements (first check)",
  "cash.vault.approve_manager": "Approve vault cash movements (final check)",
  "txn.cash_deposit": "Take cash deposits",
  "txn.cash_withdrawal": "Pay out cash withdrawals",
  "txn.transfer": "Transfer money between accounts",
  "txn.reverse": "Reverse your own transaction on the same day",
  "approval.decide": "Approve transactions above the limits",
  "vault.view": "See the vault",
  "gl.view": "See the general ledger",
  "report.operational": "See the bank's transactions",
  "eod.run": "Close the business day",
  "audit.view": "See the audit log",
};

export function abilities(codes: string[]): string[] {
  return codes.map((c) => ABILITY[c]).filter((s): s is string => !!s);
}

/** A large amount needs a manager: tell makers why a transaction may wait. */
export const LIMIT_NOTE =
  "Large amounts wait for the manager's approval before they are posted.";
