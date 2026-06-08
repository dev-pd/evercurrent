import Link from "next/link";
import { ArrowRight } from "lucide-react";
import type { CardEdge } from "@/lib/types";

interface CardEdgesListProps {
  edges: CardEdge[];
}

export function CardEdgesList({ edges }: CardEdgesListProps) {
  if (edges.length === 0) {
    return <p className="text-xs text-zinc-500">No linked cards.</p>;
  }
  return (
    <ul className="flex flex-col gap-1.5">
      {edges.map((edge) => (
        <li key={edge.id} className="flex items-center gap-2 text-sm">
          <span className="rounded-sm bg-zinc-100 px-1.5 py-0.5 text-xs font-medium text-zinc-700">
            {edge.kind}
          </span>
          <ArrowRight className="h-3 w-3 text-zinc-400" aria-hidden="true" />
          {edge.target_card_id ? (
            <Link
              href={`/decisions/${edge.target_card_id}`}
              className="text-zinc-700 hover:text-zinc-900"
            >
              {edge.target_label}
            </Link>
          ) : (
            <span className="text-zinc-700">{edge.target_label}</span>
          )}
        </li>
      ))}
    </ul>
  );
}
