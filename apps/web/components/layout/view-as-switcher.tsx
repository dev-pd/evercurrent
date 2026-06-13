"use client";

import { useQuery } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";
import { ChevronDown, Eye } from "lucide-react";
import { apiBrowser } from "@/lib/api";

const ROLE_LABEL: Record<string, string> = {
  mech: "Mechanical",
  ee: "Electrical",
  fw: "Firmware",
  sw: "Software",
  qa: "QA",
  supply: "Supply Chain",
  em: "Eng Manager",
  pm: "Product",
};

export function ViewAsSwitcher() {
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams();
  const [isPending, startTransition] = useTransition();

  const { data: members = [] } = useQuery({
    queryKey: ["members"],
    queryFn: () => apiBrowser().listMembers(),
    staleTime: 60_000,
  });

  if (members.length === 0) return null;
  const current = search.get("as") ?? members[0].id;

  function onSwitch(id: string) {
    startTransition(() => {
      router.push(`${pathname}?as=${encodeURIComponent(id)}`);
    });
  }

  return (
    <label className="relative flex items-center">
      <Eye className="pointer-events-none absolute left-2.5 h-3.5 w-3.5 text-[var(--text-muted)]" />
      <select
        aria-label="View as member"
        value={current}
        disabled={isPending}
        onChange={(e) => onSwitch(e.target.value)}
        className="appearance-none rounded-md border border-[var(--border-default)] bg-white py-1.5 pr-8 pl-8 text-xs font-medium text-[var(--text-primary)] hover:border-[var(--border-strong)] disabled:opacity-60"
      >
        {members.map((m) => (
          <option key={m.id} value={m.id}>
            {m.display_name} — {ROLE_LABEL[m.eng_role ?? ""] ?? m.eng_role ?? "Member"}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2 h-3.5 w-3.5 text-[var(--text-muted)]" />
    </label>
  );
}
