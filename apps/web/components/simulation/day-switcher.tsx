"use client";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useImpersonationStore } from "@/stores/impersonation";
import { useQuery } from "@tanstack/react-query";

const HISTORICAL = [1, 2, 3, 4, 5] as const;

function dateLabelFor(day: number, startDateIso: string | undefined): string {
  if (!startDateIso) return `Day ${day}`;
  const start = new Date(`${startDateIso}T00:00:00`);
  start.setDate(start.getDate() + (day - 1));
  return start.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function DaySwitcher() {
  const { currentProjectId, currentDay, setCurrentDay } = useImpersonationStore();
  const today = useQuery({
    queryKey: ["today", currentProjectId],
    queryFn: () => api.getToday(currentProjectId!),
    enabled: Boolean(currentProjectId),
  });
  const liveDay = today.data?.live_day;
  const startDate = today.data?.start_date;

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-zinc-500">Date</span>
      <div className="inline-flex rounded-md border border-zinc-200 bg-white">
        {HISTORICAL.map((day) => (
          <Button
            key={day}
            variant="ghost"
            size="sm"
            onClick={() => setCurrentDay(day)}
            className={cn(
              "rounded-none border-r border-zinc-200 px-3 last:border-r-0",
              currentDay === day && "bg-zinc-900 text-zinc-50 hover:bg-zinc-800",
            )}
          >
            {dateLabelFor(day, startDate)}
          </Button>
        ))}
        {liveDay !== undefined && liveDay > HISTORICAL[HISTORICAL.length - 1] && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setCurrentDay(liveDay)}
            className={cn(
              "rounded-none border-l border-zinc-200 px-3",
              currentDay === liveDay
                ? "bg-emerald-600 text-white hover:bg-emerald-700"
                : "text-emerald-700 hover:bg-emerald-50",
            )}
          >
            Today · {dateLabelFor(liveDay, startDate)}
          </Button>
        )}
      </div>
    </div>
  );
}
