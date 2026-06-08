import { auth0 } from "@/lib/auth0";
import { SignInButton } from "@/components/auth/sign-in-button";
import { UserBadge } from "@/components/auth/user-badge";
import { Button } from "@/components/ui/button";

export default async function Home() {
  const session = await auth0.getSession();
  const isAuthenticated = Boolean(session?.user);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
      <h1 className="text-2xl font-semibold">EverCurrent</h1>
      <p className="text-sm text-zinc-500">
        Pivot in progress. Dashboard rebuilds in Phase 9.
      </p>
      {isAuthenticated ? (
        <div className="flex flex-col items-center gap-3">
          <UserBadge />
          <Button asChild>
            <a href="/me-debug">Continue to /me-debug</a>
          </Button>
        </div>
      ) : (
        <SignInButton />
      )}
    </main>
  );
}
