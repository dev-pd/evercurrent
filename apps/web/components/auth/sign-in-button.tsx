"use client";

import { useUser } from "@auth0/nextjs-auth0";
import { Button } from "@/components/ui/button";

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
        Loading
      </Button>
    );
  }

  if (user) {
    return (
      <Button asChild variant="outline" size="sm">
        <a href={logoutPath}>Sign out</a>
      </Button>
    );
  }

  return (
    <Button asChild size="sm">
      <a href={loginPath}>Sign in</a>
    </Button>
  );
}
