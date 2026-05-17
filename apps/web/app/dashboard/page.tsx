"use client";

import { ChatPanel } from "@/components/chat/chat-panel";
import { DigestCard } from "@/components/digest/digest-card";
import { AppShell } from "@/components/layout/app-shell";
import { DaySwitcher } from "@/components/simulation/day-switcher";
import { PhaseSwitcher } from "@/components/simulation/phase-switcher";

export default function DashboardPage() {
  return (
    <AppShell>
      <div className="flex h-full">
        <div className="min-w-0 flex-1 overflow-auto">
          <div className="flex items-center justify-between border-b border-zinc-200 bg-white px-6 py-3">
            <DaySwitcher />
            <PhaseSwitcher />
          </div>
          <div className="p-6">
            <DigestCard />
          </div>
        </div>
        <ChatPanel />
      </div>
    </AppShell>
  );
}
