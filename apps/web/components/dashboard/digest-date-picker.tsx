"use client";

import { ChevronDown, CalendarDays } from "lucide-react";
import { formatTimestamp } from "@/lib/format-date";
import { messages } from "@/lib/messages";
import type { DigestListItem } from "@/lib/types";

const copy = messages.digest;

interface DigestDatePickerProps {
  items: DigestListItem[];
  todayIndex: number;
  selected: number;
  onSelect: (dayIndex: number) => void;
  disabled?: boolean;
}

export function DigestDatePicker({
  items,
  todayIndex,
  selected,
  onSelect,
  disabled = false,
}: DigestDatePickerProps) {
  return (
    <label className="relative flex items-center">
      <CalendarDays className="pointer-events-none absolute left-2.5 h-3.5 w-3.5 text-[var(--text-muted)]" />
      <select
        aria-label={copy.historyLabel}
        value={selected}
        disabled={disabled}
        onChange={(e) => onSelect(Number(e.target.value))}
        className="appearance-none rounded-md border border-[var(--border-default)] bg-white py-1.5 pr-8 pl-8 text-xs font-medium text-[var(--text-primary)] hover:border-[var(--border-strong)] disabled:opacity-60"
      >
        {items.map((item) => {
          const date = formatTimestamp(item.generated_at, "date") ?? item.generated_at;
          return (
            <option key={item.day_index} value={item.day_index}>
              {item.day_index === todayIndex ? copy.todayOption(date) : date}
            </option>
          );
        })}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2 h-3.5 w-3.5 text-[var(--text-muted)]" />
    </label>
  );
}
