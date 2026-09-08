import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "./apiClient";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Stage endpoints legitimately 404/409 before their stage runs — never
      // retry those. Retry other failures once.
      retry: (failureCount, error) => {
        if (error instanceof ApiError && (error.status === 404 || error.status === 409 || error.isAuth)) {
          return false;
        }
        return failureCount < 1;
      },
      refetchOnWindowFocus: false,
      staleTime: 5_000,
    },
    mutations: {
      retry: false,
    },
  },
});
