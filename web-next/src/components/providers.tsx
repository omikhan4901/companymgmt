"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Suspense, useEffect, useState, type ReactNode } from "react";
import { I18nextProvider } from "react-i18next";
import { Toaster } from "sonner";

import { ApiError } from "@/api/client";
import { SessionProvider } from "@/auth/session";
import { PageLoading } from "@/components/ui/spinner";
import i18n from "@/i18n";
import { ThemeProvider, useTheme } from "@/lib/theme";

function ThemedToaster() {
  const { resolved } = useTheme();
  return <Toaster theme={resolved} position="top-center" richColors closeButton />;
}

/**
 * Everything the product screens need. They depend on the signed-in person, so they
 * render in the browser only; the pre-rendered HTML is a loading state.
 */
export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
            staleTime: 15_000,
          },
        },
      }),
  );
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  return (
    <I18nextProvider i18n={i18n}>
      <ThemeProvider>
        <QueryClientProvider client={queryClient}>
          {mounted ? (
            <SessionProvider>
              <Suspense fallback={<PageLoading />}>{children}</Suspense>
            </SessionProvider>
          ) : (
            <PageLoading />
          )}
          <ThemedToaster />
        </QueryClientProvider>
      </ThemeProvider>
    </I18nextProvider>
  );
}
