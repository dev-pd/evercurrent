"use client";

import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { apiBrowser } from "@/lib/api";
import { useEvents } from "@/hooks/use-events";
import { messages } from "@/lib/messages";
import { useEve } from "@/stores/eve";
import { useToast } from "@/stores/toast";

const copy = messages.insights;

/**
 * App-wide listener for Eve results. Lives in the shell (not the insights page)
 * so an insight that lands while you're on another page still clears the global
 * "investigating" state and refreshes — the Run Eve button reflects it anywhere.
 */
export function EveStreamListener() {
  const router = useRouter();
  const toast = useToast();
  const done = useEve((s) => s.done);

  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: () => apiBrowser().listProjects(),
    staleTime: 300_000,
  });
  const projectId = projects?.[0]?.id ?? null;

  useEvents({
    projectId,
    enabled: !!projectId,
    onEvent: (e) => {
      if (e.type === "insight_created") {
        done();
        router.refresh();
        toast.show(copy.insightReady, "success");
      } else if (e.type === "insight_failed") {
        done();
        toast.show(copy.eveNothing, "info");
      }
    },
  });

  return null;
}
