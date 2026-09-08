import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiGet, apiPost } from "../../services/apiClient";
import { qk } from "../../services/queryKeys";
import { usePollBaseMs } from "../useSettings";
import { taskRefetchInterval } from "../usePolling";
import type { JobList, JobView } from "../../types/api";

export interface JobListParams {
  state?: string;
  type?: string;
  task_id?: string;
  limit?: number;
  offset?: number;
}

export function useJobList(params: JobListParams) {
  const query = { ...params, limit: params.limit ?? 25, offset: params.offset ?? 0 };
  return useQuery({
    queryKey: qk.jobs(query),
    queryFn: ({ signal }) => apiGet<JobList>("/jobs", { signal, query }),
  });
}

export function useJobsForTask(taskId: string | undefined, taskState: string | undefined) {
  const baseMs = usePollBaseMs();
  return useQuery({
    queryKey: qk.jobs({ task_id: taskId }),
    enabled: !!taskId,
    queryFn: ({ signal }) =>
      apiGet<JobList>("/jobs", { signal, query: { task_id: taskId, limit: 10 } }),
    refetchInterval: () =>
      taskRefetchInterval(taskState ? { state: taskState } : undefined, baseMs),
  });
}

export function useJob(id: string | undefined) {
  return useQuery({
    queryKey: qk.job(id ?? ""),
    enabled: !!id,
    queryFn: ({ signal }) => apiGet<JobView>(`/jobs/${id}`, { signal }),
  });
}

export function useCancelJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiPost<JobView>(`/jobs/${id}/cancel`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}
