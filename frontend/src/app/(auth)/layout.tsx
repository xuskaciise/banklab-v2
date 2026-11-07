import Image from "next/image";
import { ShieldCheck } from "lucide-react";
import { AuthGate } from "@/components/auth/auth-gate";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGate>
      <div className="grid min-h-screen lg:grid-cols-[minmax(0,5fr)_minmax(0,4fr)]">
        <aside className="relative hidden flex-col justify-between overflow-hidden bg-bank-navy p-10 text-white lg:flex">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -top-32 -right-32 size-96 rounded-full bg-bank-accent/20 blur-3xl"
          />
          <div className="relative flex items-center gap-3">
            <span className="flex size-11 items-center justify-center overflow-hidden rounded-xl bg-white shadow-md">
              <Image src="/logo.png" alt="SIU logo" width={44} height={44} priority />
            </span>
            <span className="text-lg font-semibold tracking-tight">BankLab</span>
          </div>
          <div className="relative max-w-md space-y-4">
            <h2 className="text-3xl leading-tight font-semibold tracking-tight">
              Learn banking by running a bank.
            </h2>
            <p className="text-sm leading-relaxed text-white/70">
              A training environment where students take real banking roles in
              class sessions, guided by their instructors.
            </p>
          </div>
          <p className="relative flex items-center gap-2 text-xs text-white/60">
            <ShieldCheck className="size-4" /> Training system. No real money or
            customer data.
          </p>
        </aside>
        <main className="flex items-center justify-center bg-surface p-6">
          <div className="w-full max-w-sm">
            <div className="mb-6 flex items-center justify-center gap-3 lg:hidden">
              <span className="flex size-10 items-center justify-center overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-border">
                <Image src="/logo.png" alt="SIU logo" width={40} height={40} />
              </span>
              <span className="text-xl font-semibold tracking-tight text-bank-navy">
                BankLab
              </span>
            </div>
            {children}
          </div>
        </main>
      </div>
    </AuthGate>
  );
}
