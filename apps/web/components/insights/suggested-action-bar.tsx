import { ArrowRight, Check, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { SuggestedAction } from "@/lib/types";

interface SuggestedActionBarProps {
  action: SuggestedAction;
}

export function SuggestedActionBar({ action }: SuggestedActionBarProps) {
  return (
    <footer className="flex flex-col gap-3 border-t border-[var(--color-accent-100)] bg-[var(--color-accent-600)] px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-start gap-3 text-white">
        <Users className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
        <div>
          <div className="flex items-center gap-1.5 text-sm font-medium">{action.label}</div>
          <div className="mt-0.5 text-xs text-white/80">{action.description}</div>
          <div className="mt-1.5 flex flex-wrap gap-1">
            {action.invitees.map((name) => (
              <span
                key={name}
                className="rounded-full bg-white/15 px-2 py-0.5 text-[10px] font-medium text-white"
              >
                {name}
              </span>
            ))}
          </div>
        </div>
      </div>
      <div className="flex gap-2 sm:flex-col">
        <Button size="sm" className="bg-white text-[var(--color-accent-700)] hover:bg-zinc-100">
          <Check className="mr-1 h-3 w-3" aria-hidden="true" />
          Yes, invite
        </Button>
        <Button
          size="sm"
          variant="outline"
          className="border-white/30 text-white hover:bg-white/10"
        >
          <ArrowRight className="mr-1 h-3 w-3" aria-hidden="true" />
          Open thread
        </Button>
      </div>
    </footer>
  );
}
