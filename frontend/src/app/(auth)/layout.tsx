import { AuthGate } from "@/components/auth/auth-gate";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGate>
      <main className="flex min-h-screen items-center justify-center bg-surface p-6">
        <div className="w-full max-w-sm">
          <p className="mb-6 text-center text-3xl font-semibold tracking-tight text-bank-navy">
            BankLab
          </p>
          {children}
        </div>
      </main>
    </AuthGate>
  );
}
