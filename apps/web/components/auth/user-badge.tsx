import { LogOut } from "lucide-react";
import { auth0 } from "@/lib/auth0";
import { messages } from "@/lib/messages";

export async function UserBadge() {
  const session = await auth0.getSession();
  if (!session?.user) {
    return null;
  }

  const email =
    typeof session.user.email === "string"
      ? session.user.email
      : (session.user.sub ?? messages.common.accountFallback);
  const initial = email.charAt(0).toUpperCase();

  return (
    <div className="flex items-center gap-2.5 border-t border-[var(--border-default)] px-3 py-3">
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[var(--color-accent-100)] text-xs font-semibold text-[var(--color-accent-700)]">
        {initial}
      </span>
      <span className="min-w-0 flex-1 truncate text-xs text-[var(--text-secondary)]">{email}</span>
      <a
        href="/api/auth/logout"
        aria-label="Sign out"
        title="Sign out"
        className="shrink-0 rounded-md p-1.5 text-[var(--text-muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
      >
        <LogOut className="h-4 w-4" aria-hidden="true" />
      </a>
    </div>
  );
}
