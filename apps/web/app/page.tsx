import { redirect } from "next/navigation";
import { auth0 } from "@/lib/auth0";
import { SignInButton } from "@/components/auth/sign-in-button";

export default async function Home() {
  const session = await auth0.getSession();
  if (session?.user) {
    redirect("/dashboard");
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
      <h1 className="text-2xl font-semibold">EverCurrent</h1>
      <p className="max-w-md text-center text-sm text-zinc-500">
        Agentic AI layer for hardware engineering teams. Sign in to see your morning briefing.
      </p>
      <SignInButton />
    </main>
  );
}
