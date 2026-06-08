import { notFound, redirect } from "next/navigation";
import { auth0 } from "@/lib/auth0";
import { apiServer } from "@/lib/api";
import { AppShell } from "@/components/layout/app-shell";
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
  const session = await auth0.getSession();
  if (!session?.user) {
    redirect("/api/auth/login");
  }
  const { id } = await params;
  const card = await safeGetCard(id);
  if (!card) {
    notFound();
  }
  return (
    <AppShell>
      <div className="mx-auto max-w-3xl">
        <KnowledgeCard card={card} />
      </div>
    </AppShell>
  );
}
