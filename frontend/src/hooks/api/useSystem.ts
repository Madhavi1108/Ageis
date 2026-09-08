import { useQuery } from "@tanstack/react-query";

import { apiGet } from "../../services/apiClient";
import { qk } from "../../services/queryKeys";
import type { HealthResponse, VersionResponse } from "../../types/api";

export function useHealth() {
  return useQuery({
    queryKey: qk.health(),
    queryFn: ({ signal }) => apiGet<HealthResponse>("/healthz", { signal }),
    refetchInterval: 15_000,
    retry: false,
  });
}

export function useVersion() {
  return useQuery({
    queryKey: qk.version(),
    queryFn: ({ signal }) => apiGet<VersionResponse>("/version", { signal }),
    retry: false,
    staleTime: 60_000,
  });
}
