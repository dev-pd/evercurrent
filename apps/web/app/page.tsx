export const dynamic = "force-dynamic";

import { redirect } from "next/navigation";
import { CircuitBoard, FileText, MessageSquare, ScanSearch } from "lucide-react";
import { auth0 } from "@/lib/auth0";
import { SignInButton } from "@/components/auth/sign-in-button";

export default async function Home() {
  const session = await auth0.getSession();
  if (session?.user) {
    redirect("/dashboard");
  }

  return (
    <main className="flex min-h-screen flex-col bg-[var(--surface-bg)]">
      <header className="flex items-center justify-between border-b border-[var(--border-default)] bg-white px-6 py-3">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-[var(--color-accent-600)] text-white">
            <CircuitBoard className="h-4 w-4" aria-hidden="true" />
          </span>
          <span className="text-sm font-semibold tracking-tight">EverCurrent</span>
        </div>
        <SignInButton />
      </header>

      <section className="mx-auto flex w-full max-w-4xl flex-1 flex-col items-start justify-center gap-8 px-6 py-16">
        <div className="flex flex-col gap-3">
          <span className="font-mono text-[11px] tracking-wider text-[var(--color-accent-700)] uppercase">
            For hardware engineering teams
          </span>
          <h1 className="max-w-2xl text-4xl font-semibold tracking-tight text-[var(--text-primary)] sm:text-5xl">
            Stop drowning in Slack. <br />
            <span className="text-[var(--text-secondary)]">See what actually changed.</span>
          </h1>
          <p className="max-w-xl text-base text-[var(--text-secondary)]">
            EverCurrent reads your team&apos;s Slack, specs, and ECOs. Surfaces decisions, risks,
            and cross-functional dependencies. Personalized to your role and the phase you&apos;re
            in.
          </p>
        </div>

        <SignInButton />

        <div className="grid w-full grid-cols-1 gap-3 sm:grid-cols-3">
          <FeatureCard
            icon={MessageSquare}
            title="Daily digest"
            body="Per-engineer briefing: what changed, what to watch, what to ignore."
          />
          <FeatureCard
            icon={FileText}
            title="Decisions log"
            body="Auto-extracted with rationale, decided-by, and source traceability."
          />
          <FeatureCard
            icon={ScanSearch}
            title="Document graph"
            body="Specs, BOMs, FAI reports indexed alongside team chatter."
          />
        </div>
      </section>

      <footer className="border-t border-[var(--border-default)] bg-white px-6 py-4 text-[11px] text-[var(--text-muted)]">
        <span className="font-mono">v0.12.0</span> · take-home build
      </footer>
    </main>
  );
}

function FeatureCard({
  icon: Icon,
  title,
  body,
}: {
  icon: typeof CircuitBoard;
  title: string;
  body: string;
}) {
  return (
    <div className="rounded-lg border border-[var(--border-default)] bg-white p-4">
      <Icon className="h-4 w-4 text-[var(--color-accent-600)]" aria-hidden="true" />
      <h3 className="mt-2 text-sm font-semibold text-[var(--text-primary)]">{title}</h3>
      <p className="mt-1 text-xs text-[var(--text-muted)]">{body}</p>
    </div>
  );
}
