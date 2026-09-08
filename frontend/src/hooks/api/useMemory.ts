import { useMutation, useQuery } from "@tanstack/react-query";

import { apiGet, apiPost } from "../../services/apiClient";
import { qk } from "../../services/queryKeys";
import type { EngineeringMemoryOut, MemoryHit, MemorySearchRequest } from "../../types/api";

export function useMemoryList(repositoryId?: string) {
  return useQuery({
    queryKey: qk.memoryList(repositoryId),
    queryFn: ({ signal }) =>
      apiGet<EngineeringMemoryOut[]>("/memory", {
        signal,
        query: { repository_id: repositoryId, limit: 50 },
      }),
  });
}

export function useMemorySearch() {
  return useMutation({
    mutationFn: (body: MemorySearchRequest) => apiPost<MemoryHit[]>("/memory/search", body),
  });
}
