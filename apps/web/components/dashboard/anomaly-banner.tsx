import Link from "next/link";
import { AlertTriangle } from "lucide-react";
import type { DigestAnomaly } from "@/lib/types";

interface AnomalyBannerProps {
  anomalies: DigestAnomaly[];
}

export function AnomalyBanner({ anomalies }: AnomalyBannerProps) {
  if (anomalies.length === 0) return null;

  return (
    <section
      aria-label="Anomalies"
      className="rounded-lg border border-amber-200 bg-amber-50 p-4"
    >
      <header className="mb-2 flex items-center gap-2">
        <AlertTriangle className="h-4 w-4 text-amber-600" aria-hidden="true" />
        <h2 className="text-sm font-semibold text-amber-900">You might be missing</h2>
        <span className="text-xs text-amber-700">({anomalies.length})</span>
      </header>
      <ul className="flex flex-col gap-2">
        {anomalies.map((anomaly) => (
          <li key={anomaly.id} className="text-sm text-amber-900">
            <span>{anomaly.summary}</span>
            {anomaly.card_id && (
              <Link
                href={`/decisions/${anomaly.card_id}`}
                className="ml-2 text-xs font-medium text-amber-700 underline hover:text-amber-900"
              >
                Open
              </Link>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
