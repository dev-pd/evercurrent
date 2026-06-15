"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, useTransition } from "react";
import { ChevronDown, Eye, Loader2 } from "lucide-react";
import { apiBrowser, VIEW_AS_COOKIE } from "@/lib/api";
import { roleLabel } from "@/lib/roles";

function readCookie(): string | null {
  if (typeof document === "undefined") return null;
  const hit = document.cookie.split("; ").find((c) => c.startsWith(`${VIEW_AS_COOKIE}=`));
  return hit ? decodeURIComponent(hit.split("=")[1]) : null;
}

export function ViewAsSwitcher() {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [switching, setSwitching] = useState(false);
  const sawPending = useRef(false);

  const { data: members = [] } = useQuery({
    queryKey: ["members"],
    queryFn: () => apiBrowser().listMembers(),
    staleTime: 60_000,
  });

  // Clear the overlay when the refresh transition settles (true -> false edge).
  useEffect(() => {
    if (isPending) {
      sawPending.current = true;
    } else if (sawPending.current) {
      sawPending.current = false;
      setSwitching(false);
    }
  }, [isPending]);

  // Safety net: never let the overlay stick if the transition never settles.
  useEffect(() => {
    if (!switching) return undefined;
    const t = setTimeout(() => setSwitching(false), 4000);
    return () => clearTimeout(t);
  }, [switching]);

  if (members.length === 0) return null;
  const current = readCookie() ?? members[0].id;

  function onSwitch(id: string) {
    if (id === current) return;
    setSwitching(true);
    document.cookie = `${VIEW_AS_COOKIE}=${encodeURIComponent(id)}; path=/; max-age=86400; samesite=lax`;
    startTransition(() => {
      router.refresh();
    });
  }

  return (
    <>
      <label className="relative flex items-center">
        <Eye className="pointer-events-none absolute left-2.5 h-3.5 w-3.5 text-[var(--text-muted)]" />
        <select
          aria-label="View as member"
          value={current}
          disabled={switching}
          onChange={(e) => onSwitch(e.target.value)}
          className="appearance-none rounded-md border border-[var(--border-default)] bg-white py-1.5 pr-8 pl-8 text-xs font-medium text-[var(--text-primary)] hover:border-[var(--border-strong)] disabled:opacity-60"
        >
          {members.map((m) => (
            <option key={m.id} value={m.id}>
              {m.display_name} — {roleLabel(m.eng_role)}
            </option>
          ))}
        </select>
        <ChevronDown className="pointer-events-none absolute right-2 h-3.5 w-3.5 text-[var(--text-muted)]" />
      </label>

      {switching && (
        <div
          aria-live="polite"
          aria-busy="true"
          className="fixed inset-0 z-50 flex items-center justify-center bg-white/55 backdrop-blur-[2px]"
        >
          <div className="flex flex-col items-center gap-2">
            <Loader2 className="h-7 w-7 animate-spin text-[var(--color-accent-600)]" />
            <span className="text-xs font-medium text-[var(--text-secondary)]">
              Switching view…
            </span>
          </div>
        </div>
      )}
    </>
  );
}
