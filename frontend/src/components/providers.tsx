"use client";

import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import { TooltipProvider } from "@/components/ui/tooltip";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
      }),
  );
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider delay={200}>{children}</TooltipProvider>
      <Toaster
        theme="light"
        position="bottom-right"
        toastOptions={{
          classNames: {
            toast:
              "!rounded-lg !border !border-border !bg-card !text-text-strong !shadow-lg",
            description: "!text-text-muted",
            success: "[&_[data-icon]]:!text-fin-success",
            error: "[&_[data-icon]]:!text-fin-danger",
          },
        }}
      />
    </QueryClientProvider>
  );
}
