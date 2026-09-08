import { useMutation, useQuery } from "@tanstack/react-query";

import { apiGet, apiPost } from "../../services/apiClient";
import { qk } from "../../services/queryKeys";
import type { GitHubIssueInfo, GitHubRepoInfo, IssueRef } from "../../types/api";

export function useGithubIssue(
  owner: string | undefined,
  repo: string | undefined,
  number: number | undefined,
  opts?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: qk.githubIssue(owner ?? "", repo ?? "", number ?? 0),
    enabled: !!owner && !!repo && !!number && (opts?.enabled ?? false),
    retry: false,
    queryFn: ({ signal }) =>
      apiGet<GitHubIssueInfo>(`/github/repos/${owner}/${repo}/issues/${number}`, { signal }),
  });
}

export function useGithubRepo(owner: string | undefined, repo: string | undefined) {
  return useQuery({
    queryKey: qk.githubRepo(owner ?? "", repo ?? ""),
    enabled: !!owner && !!repo,
    retry: false,
    queryFn: ({ signal }) =>
      apiGet<GitHubRepoInfo>(`/github/repos/${owner}/${repo}`, { signal }),
  });
}

export function useImportGithubIssue() {
  // Persists an Issue row (repository_id is a query param). The dashboard mainly
  // uses the issue fetch above to prefill the Create Task form instead.
  return useMutation({
    mutationFn: (args: { owner: string; repo: string; number: number; repository_id: string }) =>
      apiPost<IssueRef>(
        `/github/repos/${args.owner}/${args.repo}/issues/${args.number}/import`,
        undefined,
        { query: { repository_id: args.repository_id } },
      ),
  });
}
