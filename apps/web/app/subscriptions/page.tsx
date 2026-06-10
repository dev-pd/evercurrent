export const dynamic = "force-dynamic";

import { redirect } from "next/navigation";
import { auth0 } from "@/lib/auth0";
import { AppShell } from "@/components/layout/app-shell";

interface Topic {
  key: string;
  label: string;
  description: string;
}

const TOPICS: Topic[] = [
  { key: "chassis", label: "Chassis", description: "Mechanical structures, brackets, enclosures." },
  { key: "power", label: "Power", description: "PMIC, battery, thermals, regulation." },
  { key: "firmware", label: "Firmware", description: "Bootloader, drivers, OTA, RTOS." },
  { key: "qa", label: "QA & Testing", description: "FAI, reliability, compliance, EVT/DVT/PVT." },
  { key: "supply_chain", label: "Supply chain", description: "Vendor swaps, lead time, BOM cost." },
  { key: "compliance", label: "Compliance", description: "FCC, CE, safety, regulatory." },
];

export default async function SubscriptionsPage() {
  const session = await auth0.getSession();
  if (!session?.user) {
    redirect("/api/auth/login?returnTo=/subscriptions");
  }
  return (
    <AppShell>
      <div className="mx-auto flex max-w-3xl flex-col gap-8">
        <header className="border-b border-zinc-200 pb-4">
          <h1 className="text-2xl font-semibold tracking-tight">Subscriptions</h1>
          <p className="mt-1 text-sm text-zinc-500">
            Pick the subsystems and channels that drive your digest. Cross-domain
            risks always surface regardless.
          </p>
        </header>

        <section className="flex flex-col gap-3">
          <h2 className="text-sm font-semibold text-zinc-900">Subsystems</h2>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {TOPICS.map((t) => (
              <label
                key={t.key}
                className="flex cursor-pointer items-start gap-3 rounded-lg border border-zinc-200 bg-white p-3 hover:border-zinc-300"
              >
                <input
                  type="checkbox"
                  className="mt-0.5 h-4 w-4 rounded border-zinc-300 text-zinc-900 focus:ring-zinc-900"
                  disabled
                />
                <div className="flex-1">
                  <div className="text-sm font-medium text-zinc-900">{t.label}</div>
                  <div className="mt-0.5 text-xs text-zinc-500">{t.description}</div>
                </div>
              </label>
            ))}
          </div>
          <p className="text-xs text-zinc-400">
            Editing saves to your profile and re-scores incoming messages. Persistence wires up once auth is fully bound.
          </p>
        </section>
      </div>
    </AppShell>
  );
}
