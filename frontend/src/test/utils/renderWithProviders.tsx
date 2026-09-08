import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderOptions } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ToastProvider } from "../../components/feedback/Toast";
import { SettingsProvider } from "../../hooks/useSettings";
import { _resetSettingsCache } from "../../services/settingsStore";

export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

interface Options extends Omit<RenderOptions, "wrapper"> {
  route?: string;
  path?: string;
  queryClient?: QueryClient;
}

export function renderWithProviders(ui: ReactElement, opts: Options = {}) {
  const { route = "/", path, queryClient = makeQueryClient(), ...rest } = opts;
  try {
    localStorage.clear();
  } catch {
    /* ignore */
  }
  _resetSettingsCache();

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <SettingsProvider>
          <ToastProvider>
            <MemoryRouter initialEntries={[route]}>
              {path ? (
                <Routes>
                  <Route path={path} element={children} />
                </Routes>
              ) : (
                children
              )}
            </MemoryRouter>
          </ToastProvider>
        </SettingsProvider>
      </QueryClientProvider>
    );
  }

  return { queryClient, ...render(ui, { wrapper: Wrapper, ...rest }) };
}
