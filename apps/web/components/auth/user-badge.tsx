import { auth0 } from "@/lib/auth0";

export async function UserBadge() {
  const session = await auth0.getSession();
  if (!session?.user) {
    return null;
  }

  const email = typeof session.user.email === "string" ? session.user.email : session.user.sub;

  return (
    <div className="flex items-center gap-3 rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm">
      <span className="text-zinc-700">{email}</span>
      <a
        href="/api/auth/logout"
        className="text-xs font-medium text-zinc-500 hover:text-zinc-900"
      >
        Sign out
      </a>
    </div>
  );
}
