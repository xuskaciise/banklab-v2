"use client";

import { Building2, CheckCircle2, Lock, UserCheck } from "lucide-react";
import { STATUS_LABEL, useMyTellerSession, useTillAvailability } from "@/lib/tellers";
import { StatCard } from "@/components/shared/stat-card";

/** Totals come straight from the tills list; nothing is computed for money. */
export function TillStats({ sid }: { sid: string }) {
  const tills = useTillAvailability(sid);
  const mine = useMyTellerSession(sid);
  const list = tills.data ?? [];
  const free = list.filter((t) => t.available).length;
  const s = mine.data;
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard
        label="Total tills"
        icon={Building2}
        loading={tills.isPending}
        value={list.length}
        hint="In this bank"
      />
      <StatCard
        label="Available"
        icon={CheckCircle2}
        loading={tills.isPending}
        value={<span className="text-fin-success">{free}</span>}
        hint="Free to open"
      />
      <StatCard
        label="Occupied"
        icon={Lock}
        loading={tills.isPending}
        value={<span className="text-fin-pending">{list.length - free}</span>}
        hint="In use or waiting"
      />
      <StatCard
        label="My current till"
        icon={UserCheck}
        loading={mine.isPending}
        value={s ? <span className="font-mono">{s.till_code}</span> : "None today"}
        hint={s ? (STATUS_LABEL[s.status] ?? s.status) : "Request one below"}
      />
    </div>
  );
}
