import Image from "next/image";
import {
  Banknote,
  Calculator,
  IdCard,
  ShieldCheck,
  UserCog,
  Vault,
} from "lucide-react";
import { AuthGate } from "@/components/auth/auth-gate";

// The bank roles students take on, and what each one is responsible for.
const ROLES = [
  {
    icon: UserCog,
    role: "Manager",
    text: "approves transactions above limits, oversees the branch and closes the business day.",
  },
  {
    icon: Banknote,
    role: "Teller",
    text: "serves customers at the counter: deposits, withdrawals, cheques and a balanced till.",
  },
  {
    icon: IdCard,
    role: "Customer Service",
    text: "onboards customers, completes KYC and opens their accounts.",
  },
  {
    icon: Vault,
    role: "Vault Custodian",
    text: "guards the vault cash and supplies the tellers under dual control.",
  },
  {
    icon: Calculator,
    role: "Accountant",
    text: "keeps the ledger balanced and reads the bank's financial reports.",
  },
] as const;

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGate>
      <div className="grid min-h-screen lg:grid-cols-[minmax(0,5fr)_minmax(0,4fr)]">
        <aside className="relative hidden flex-col justify-between overflow-hidden bg-bank-navy p-10 text-white lg:flex">
          <Image
            src="/bank.jpg"
            alt=""
            fill
            priority
            sizes="(min-width: 1024px) 56vw, 0px"
            className="object-cover"
          />
          {/* Navy wash keeps the copy readable over the photo. */}
          <div
            aria-hidden="true"
            className="absolute inset-0 bg-gradient-to-t from-bank-navy via-bank-navy/80 to-bank-navy/40"
          />
          <div className="relative flex items-center gap-3">
            <span className="flex size-11 items-center justify-center overflow-hidden rounded-xl bg-white shadow-md">
              <Image
                src="/logo.png"
                alt="SIU logo"
                width={44}
                height={44}
                priority
              />
            </span>
            <span className="text-lg font-semibold tracking-tight">
              BankLab
            </span>
          </div>
          <div className="relative max-w-lg space-y-5">
            <h2 className="text-3xl leading-tight font-semibold tracking-tight">
              From the classroom to inside the bank.
            </h2>
            <p className="text-sm leading-relaxed text-white/80">
              BankLab turns banking theory into real practice. Students step
              inside a working bank as its staff and carry every responsibility
              the bank runs on.
            </p>
            <ul className="space-y-3 pt-1">
              {ROLES.map(({ icon: Icon, role, text }) => (
                <li
                  key={role}
                  className="flex items-start gap-3 text-sm leading-snug text-white/80"
                >
                  <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg bg-white/10 ring-1 ring-white/20">
                    <Icon className="size-4 text-white" aria-hidden="true" />
                  </span>
                  <span>
                    <span className="font-semibold text-white">{role}</span>{" "}
                    {text}
                  </span>
                </li>
              ))}
            </ul>
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
