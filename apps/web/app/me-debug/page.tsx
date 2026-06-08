import { redirect } from "next/navigation";
import { auth0 } from "@/lib/auth0";

export default async function MeDebugPage() {
  const session = await auth0.getSession();
  if (!session?.user) {
    redirect("/api/auth/login");
  }

  return (
    <main className="flex min-h-screen flex-col gap-4 p-8">
      <h1 className="text-2xl font-semibold">/me-debug</h1>
      <p className="text-sm text-zinc-500">
        Raw Auth0 session. Phase 9 replaces this with the real dashboard.
      </p>
      <pre className="overflow-auto rounded-md border border-zinc-200 bg-zinc-50 p-4 text-xs text-zinc-800">
        {JSON.stringify(session.user, null, 2)}
      </pre>
      <a href="/api/auth/logout" className="text-xs text-zinc-500 hover:text-zinc-900">
        Sign out
      </a>
    </main>
  );
}
