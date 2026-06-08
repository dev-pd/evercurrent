"use client";

import { Auth0Provider } from "@auth0/nextjs-auth0";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 5_000, refetchOnWindowFocus: false },
        },
      }),
  );
  return (
    <Auth0Provider>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </Auth0Provider>
  );
}
