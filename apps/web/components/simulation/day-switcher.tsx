"use client";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useImpersonationStore } from "@/stores/impersonation";

const DAYS = [1, 2, 3, 4, 5];

export function DaySwitcher() {
  const { currentDay, setCurrentDay } = useImpersonationStore();
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-zinc-500">Day</span>
      <div className="inline-flex rounded-md border border-zinc-200 bg-white">
        {DAYS.map((day) => (
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
            {day}
          </Button>
        ))}
      </div>
    </div>
  );
}
