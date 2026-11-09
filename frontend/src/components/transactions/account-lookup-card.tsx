"use client";

import type { AccountOut } from "@/lib/api/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AccountPicker } from "./account-picker";

/** "Account Information" card: one lookup, or From + To for transfers. */
export function AccountLookupCard({
  sid,
  transfer,
  from,
  to,
  onFrom,
  onTo,
  errs,
}: {
  sid: string;
  transfer: boolean;
  from: AccountOut | null;
  to: AccountOut | null;
  onFrom: (a: AccountOut | null) => void;
  onTo: (a: AccountOut | null) => void;
  errs: Record<string, string>;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Account Information</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <AccountPicker
          sid={sid}
          label={transfer ? "From Account" : "Account Number"}
          value={from}
          onChange={onFrom}
        />
        {errs.from && <p className="text-sm text-fin-danger">{errs.from}</p>}
        {transfer && (
          <>
            <hr className="border-border" />
            <AccountPicker sid={sid} label="To Account" value={to} onChange={onTo} />
            {errs.to && <p className="text-sm text-fin-danger">{errs.to}</p>}
          </>
        )}
      </CardContent>
    </Card>
  );
}
