import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";

import { ErrorBoundary } from "./components/feedback/ErrorBoundary";
import { ToastProvider } from "./components/feedback/Toast";
import { SettingsProvider } from "./hooks/useSettings";
import { queryClient } from "./services/queryClient";
import { router } from "./router";

export function App() {
  return (
    <ErrorBoundary fallbackTitle="The dashboard failed to start.">
      <QueryClientProvider client={queryClient}>
        <SettingsProvider>
          <ToastProvider>
            <RouterProvider router={router} />
          </ToastProvider>
        </SettingsProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
