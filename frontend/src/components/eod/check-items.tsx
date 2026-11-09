import Link from "next/link";
import { formatMoney } from "@/lib/banking";
import { StatusBadge } from "@/components/shared/status-badge";
import type { EodCheck } from "@/lib/api/types";

type Row = Record<string, unknown>;
const s = (v: unknown) => String(v ?? "");

const th = "px-2 py-1.5 text-left text-xs font-medium text-text-muted";
const amt = "px-2 py-1.5 text-right tabular-nums";

export function CheckItems({ check, sid }: { check: EodCheck; sid: string }) {
  const items = check.items as Row[];
  if (check.ok || items.length === 0) return null;

  if (check.code === "teller_sessions_closed")
    return (
      <ul className="mt-3 divide-y divide-border rounded-md border border-border text-sm">
        {items.map((i) => (
          <li key={s(i.id)} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
            <span className="text-text-body">
              {s(i.teller_name)} <span className="text-text-muted">· till {s(i.till_code)}</span>
            </span>
            <StatusBadge status={s(i.status)} />
          </li>
        ))}
      </ul>
    );

  if (check.code === "no_pending_approvals")
    return (
      <ul className="mt-3 divide-y divide-border rounded-md border border-border text-sm">
        {items.map((i) => (
          <li key={s(i.kind)} className="flex items-center justify-between px-3 py-2">
            <span className="text-text-body capitalize">{s(i.kind).replace("_", " ")}</span>
            <Link href={`/s/${sid}/approvals`} className="font-medium text-bank-primary hover:underline">
              {s(i.count)} pending
            </Link>
          </li>
        ))}
      </ul>
    );

  const money = (v: unknown, c: unknown) => formatMoney(s(v), s(c));
  const recon = check.code === "cash_reconciliation";
  return (
    <div className="mt-3 overflow-x-auto rounded-md border border-border">
      <table className="w-full text-sm">
        <thead className="bg-hover">
          <tr>
            <th className={th}>Currency</th>
            {recon ? (
              <>
                <th className={`${th} text-right`}>Vault total</th>
                <th className={`${th} text-right`}>GL vault</th>
                <th className={`${th} text-right`}>Teller total</th>
                <th className={`${th} text-right`}>GL teller</th>
              </>
            ) : (
              <>
                <th className={`${th} text-right`}>Debit</th>
                <th className={`${th} text-right`}>Credit</th>
              </>
            )}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {items.map((i, n) => (
            <tr key={n}>
              <td className="px-2 py-1.5 font-medium text-text-strong">{s(i.currency)}</td>
              {recon ? (
                <>
                  <td className={amt}>{money(i.vault_total, i.currency)}</td>
                  <td className={amt}>{money(i.gl_vault, i.currency)}</td>
                  <td className={amt}>{money(i.teller_total, i.currency)}</td>
                  <td className={amt}>{money(i.gl_teller, i.currency)}</td>
                </>
              ) : (
                <>
                  <td className={`${amt} text-fin-danger`}>Dr {money(i.debit, i.currency)}</td>
                  <td className={`${amt} text-fin-success`}>Cr {money(i.credit, i.currency)}</td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
