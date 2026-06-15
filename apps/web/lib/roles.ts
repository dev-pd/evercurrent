export const ENG_ROLES = [
  { value: "mech", label: "Mechanical" },
  { value: "ee", label: "Electrical" },
  { value: "fw", label: "Firmware" },
  { value: "sw", label: "Software" },
  { value: "design", label: "Industrial Design" },
  { value: "qa", label: "QA" },
  { value: "supply", label: "Supply chain" },
  { value: "em", label: "Eng manager" },
  { value: "pm", label: "Product" },
] as const;

export type EngRole = (typeof ENG_ROLES)[number]["value"];

const ROLE_LABEL: Record<string, string> = Object.fromEntries(
  ENG_ROLES.map((r) => [r.value, r.label]),
);

export function roleLabel(value: string | null | undefined): string {
  if (!value) return "Member";
  return ROLE_LABEL[value] ?? value;
}
