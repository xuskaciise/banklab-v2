import { SystemStatus } from "@/components/dashboard/system-status";

export default function Home() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-text-strong">Dashboard</h1>
      <SystemStatus />
    </div>
  );
}
