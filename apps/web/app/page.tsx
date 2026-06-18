export const dynamic = "force-dynamic";

import { redirect } from "next/navigation";
import { CircuitBoard, FileText, MessageSquare, ScanSearch } from "lucide-react";
import { auth0 } from "@/lib/auth0";
import { SignInButton } from "@/components/auth/sign-in-button";
import { CircuitArt } from "@/components/landing/circuit-art";
import { messages } from "@/lib/messages";

const copy = messages.landing;

export default async function Home() {
  const session = await auth0.getSession();
  if (session?.user) {
    redirect("/dashboard");
  }

  return (
    <main className="flex min-h-screen flex-col bg-[var(--surface-bg)]">
      <header className="border-b border-[var(--border-default)] bg-white">
        <div className="mx-auto flex w-full max-w-4xl items-center justify-between px-6 py-3">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-md bg-[var(--color-accent-600)] text-white">
              <CircuitBoard className="h-4 w-4" aria-hidden="true" />
            </span>
            <span className="text-sm font-semibold tracking-tight">{messages.common.brand}</span>
          </div>
          <SignInButton />
        </div>
      </header>

      <section className="mx-auto flex w-full max-w-4xl flex-1 flex-col justify-center gap-12 px-6 py-16">
        <div className="grid items-center gap-10 lg:grid-cols-2">
          <div className="flex flex-col items-start gap-6">
            <div className="flex flex-col gap-3">
              <span className="font-mono text-[11px] tracking-wider text-[var(--color-accent-700)] uppercase">
                {copy.eyebrow}
              </span>
              <h1 className="text-4xl font-semibold tracking-tight text-[var(--text-primary)] sm:text-5xl">
                {copy.headlineLine1} <br />
                <span className="text-[var(--text-secondary)]">{copy.headlineLine2}</span>
              </h1>
              <p className="text-base text-[var(--text-secondary)]">{copy.lede}</p>
            </div>
            <SignInButton />
          </div>
          <CircuitArt className="mx-auto" />
        </div>

        <div className="grid w-full grid-cols-1 gap-3 sm:grid-cols-3">
          <FeatureCard
            icon={MessageSquare}
            title={copy.features.digestTitle}
            body={copy.features.digestBody}
          />
          <FeatureCard
            icon={FileText}
            title={copy.features.decisionsTitle}
            body={copy.features.decisionsBody}
          />
          <FeatureCard
            icon={ScanSearch}
            title={copy.features.graphTitle}
            body={copy.features.graphBody}
          />
        </div>
      </section>

      <footer className="border-t border-[var(--border-default)] bg-white px-6 py-4 text-[11px] text-[var(--text-muted)]">
        <span className="font-mono">{copy.version}</span> · {copy.buildNote}
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
