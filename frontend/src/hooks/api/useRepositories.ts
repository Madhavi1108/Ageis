import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiGet, apiPost } from "../../services/apiClient";
import { qk } from "../../services/queryKeys";
import { rememberRepoId } from "../../services/settingsStore";
import type {
  GitContext,
  IngestRequest,
  IngestResult,
  RepositoryCreateRequest,
  RepositoryHealthProfile,
  RepositoryRef,
} from "../../types/api";

export function useRepository(id: string | undefined) {
  return useQuery({
    queryKey: qk.repo(id ?? ""),
    enabled: !!id,
    queryFn: ({ signal }) => apiGet<RepositoryRef>(`/repositories/${id}`, { signal }),
  });
}

export function useRepositoryHealth(id: string | undefined, opts?: { enabled?: boolean }) {
  return useQuery({
    queryKey: qk.repoHealth(id ?? ""),
    enabled: !!id && (opts?.enabled ?? true),
    queryFn: ({ signal }) =>
      apiGet<RepositoryHealthProfile>(`/repositories/${id}/health`, { signal }),
  });
}

export function useGitContext(id: string | undefined, opts?: { enabled?: boolean }) {
  return useQuery({
    queryKey: qk.repoGit(id ?? "", "context"),
    enabled: !!id && (opts?.enabled ?? true),
    queryFn: ({ signal }) =>
      apiGet<GitContext>(`/repositories/${id}/git/context`, { signal, query: { limit: 50 } }),
  });
}

export function useCreateRepository() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: RepositoryCreateRequest) => apiPost<RepositoryRef>("/repositories", body),
    onSuccess: (repo) => {
      rememberRepoId(repo.id);
      qc.setQueryData(qk.repo(repo.id), repo);
    },
  });
}

export function useCreateSnapshot(repositoryId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: IngestRequest) =>
      apiPost<IngestResult>(`/repositories/${repositoryId}/snapshots`, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: qk.repo(repositoryId) });
      void qc.invalidateQueries({ queryKey: qk.repoHealth(repositoryId) });
    },
  });
}
