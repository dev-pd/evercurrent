"use client";

import { useUser } from "@auth0/nextjs-auth0";
import { Button } from "@/components/ui/button";
import { messages } from "@/lib/messages";

const copy = messages.auth;

interface SignInButtonProps {
  loginPath?: string;
  logoutPath?: string;
}

export function SignInButton({
  loginPath = "/api/auth/login",
  logoutPath = "/api/auth/logout",
}: SignInButtonProps) {
  const { user, isLoading } = useUser();

  if (isLoading) {
    return (
      <Button variant="outline" size="sm" disabled>
        {copy.loading}
      </Button>
    );
  }

  if (user) {
    return (
      <Button asChild variant="outline" size="sm">
        <a href={logoutPath}>{copy.signOut}</a>
      </Button>
    );
  }

  return (
    <Button asChild size="sm">
      <a href={loginPath}>{copy.signIn}</a>
    </Button>
  );
}
