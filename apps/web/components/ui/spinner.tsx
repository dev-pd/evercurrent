"use client";

import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";

interface SpinnerProps {
  className?: string;
  size?: "xs" | "sm" | "md" | "lg";
  label?: string;
}

const SIZE: Record<NonNullable<SpinnerProps["size"]>, string> = {
  xs: "h-3 w-3",
  sm: "h-4 w-4",
  md: "h-5 w-5",
  lg: "h-6 w-6",
};

export function Spinner({ className, size = "sm", label }: SpinnerProps) {
  return (
    <span
      className={cn("inline-flex items-center gap-2 text-zinc-500", className)}
      role="status"
      aria-live="polite"
    >
      <Loader2 className={cn("animate-spin", SIZE[size])} aria-hidden="true" />
      {label && <span className="text-xs">{label}</span>}
    </span>
  );
}
