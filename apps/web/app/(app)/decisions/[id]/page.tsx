export const dynamic = "force-dynamic";

import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { apiServer } from "@/lib/api";
import { PageContainer } from "@/components/layout/page-header";
import { SignalCard } from "@/components/signals/signal-card";
import { messages } from "@/lib/messages";
import type { SignalResponse } from "@/lib/types";

async function safeGetSignal(id: string): Promise<SignalResponse | null> {
  try {
    const client = await apiServer();
    return await client.getSignal(id);
  } catch (error) {
    if (process.env.NODE_ENV !== "production") {
      console.warn("signal fetch failed", error);
    }
    return null;
  }
}

interface SignalDetailPageProps {
  params: Promise<{ id: string }>;
}

export default async function SignalDetailPage({ params }: SignalDetailPageProps) {
  const { id } = await params;
  const signal = await safeGetSignal(id);
  if (!signal) {
    notFound();
  }
  return (
    <PageContainer
      header={
        <Link
          href="/decisions"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          {messages.decisions.backToDecisions}
        </Link>
      }
    >
      <div className="mx-auto w-full max-w-3xl">
        <SignalCard signal={signal} />
      </div>
    </PageContainer>
  );
}
