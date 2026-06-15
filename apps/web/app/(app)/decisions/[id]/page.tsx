export const dynamic = "force-dynamic";

import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { apiServer } from "@/lib/api";
import { PageContainer } from "@/components/layout/page-header";
import { KnowledgeCard } from "@/components/cards/knowledge-card";
import type { CardResponse } from "@/lib/types";

async function safeGetCard(id: string): Promise<CardResponse | null> {
  try {
    const client = await apiServer();
    return await client.getCard(id);
  } catch (error) {
    if (process.env.NODE_ENV !== "production") {
      console.warn("card fetch failed", error);
    }
    return null;
  }
}

interface CardDetailPageProps {
  params: Promise<{ id: string }>;
}

export default async function CardDetailPage({ params }: CardDetailPageProps) {
  const { id } = await params;
  const card = await safeGetCard(id);
  if (!card) {
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
          Back to Decisions
        </Link>
      }
    >
      <div className="mx-auto w-full max-w-3xl">
        <KnowledgeCard card={card} />
      </div>
    </PageContainer>
  );
}
