"use client";

import Link from "next/link";
import { formatMoney } from "@/lib/banking";
import { useMyTellerSession } from "@/lib/tellers";
import { useApprovals, useTransactions } from "@/lib/transactions";
import { abilities, LIMIT_NOTE, QUICK_ACTIONS } from "@/lib/role-guide";
import { SessionStatus } from "@/components/tellers/session-bits";

function Tile({
  label,
  children,
  href,
}: {
  label: string;
  children: React.ReactNode;
  href?: string;
}) {
  const body = (
    <div className="h-full rounded-xl border border-border bg-card p-4 shadow-xs">
      <p className="text-xs font-medium uppercase tracking-wide text-text-muted">
        {label}
      </p>
      <div className="mt-2 text-text-strong">{children}</div>
    </div>
  );
  return href ? (
    <Link href={href} className="block hover:opacity-90">
      {body}
    </Link>
  ) : (
    body
  );
}

function TillTile({ sid }: { sid: string }) {
  const mine = useMyTellerSession(sid);
  const t = mine.data;
  return (
    <Tile label="My till" href={`/s/${sid}/teller/till`}>
      {!t ? (
        <p className="text-sm text-text-muted">
          No till today. Open one to start serving customers.
        </p>
      ) : (
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="font-semibold">{t.till_code}</span>
            <SessionStatus status={t.status} />
          </div>
          {t.balances.map((b) => (
            <p key={b.currency} className="text-lg font-semibold tabular-nums">
              {formatMoney(b.balance, b.currency)}
            </p>
          ))}
        </div>
      )}
    </Tile>
  );
}

function CountTile({
  label,
  count,
  href,
  hint,
}: {
  label: string;
  count?: number;
  href: string;
  hint: string;
}) {
  return (
    <Tile label={label} href={href}>
      <p className="text-2xl font-semibold tabular-nums">{count ?? "–"}</p>
      <p className="text-sm text-text-muted">{hint}</p>
    </Tile>
  );
}

function WaitingTile({ sid }: { sid: string }) {
  const q = useTransactions(sid, { status: "pending_approval" });
  return (
    <CountTile
      label="Waiting for approval"
      count={q.data?.count}
      href={`/s/${sid}/transactions`}
      hint="Transactions the manager has not decided yet"
    />
  );
}

function ApprovalsTile({ sid }: { sid: string }) {
  const q = useApprovals(sid);
  return (
    <CountTile
      label="Approvals to decide"
      count={q.data?.length}
      href={`/s/${sid}/approvals`}
      hint="Transactions above a limit"
    />
  );
}

export function RoleHome({ sid, codes }: { sid: string; codes: string[] }) {
  const has = (c: string) => codes.includes(c);
  const isTeller = has("till.open.request") || has("till.close");
  const makes = has("txn.cash_deposit") || has("txn.transfer");
  const actions = QUICK_ACTIONS.filter((a) => a.any.some(has));
  const can = abilities(codes);
  return (
    <div className="space-y-6">
      {(isTeller || makes || has("approval.decide")) && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {isTeller && <TillTile sid={sid} />}
          {makes && has("report.operational") && <WaitingTile sid={sid} />}
          {has("approval.decide") && <ApprovalsTile sid={sid} />}
        </div>
      )}

      {actions.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-text-strong">
            Start here
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {actions.map((a) => (
              <Link
                key={a.title}
                href={a.href(sid)}
                className="rounded-xl border border-border bg-card p-4 shadow-xs hover:border-bank-accent"
              >
                <p className="font-semibold text-bank-primary">{a.title}</p>
                <p className="mt-1 text-sm text-text-muted">{a.text}</p>
              </Link>
            ))}
          </div>
        </section>
      )}

      {can.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-base font-semibold text-text-strong">
            What you can do in this role
          </h2>
          <ul className="list-disc space-y-1 pl-5 text-sm text-text-muted">
            {can.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
          {makes && <p className="text-sm text-text-muted">{LIMIT_NOTE}</p>}
        </section>
      )}
    </div>
  );
}
