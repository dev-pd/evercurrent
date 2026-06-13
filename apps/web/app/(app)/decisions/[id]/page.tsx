export const dynamic = "force-dynamic";

import { notFound } from "next/navigation";
import { apiServer } from "@/lib/api";
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
    <div className="mx-auto max-w-3xl">
      <KnowledgeCard card={card} />
    </div>
  );
}
