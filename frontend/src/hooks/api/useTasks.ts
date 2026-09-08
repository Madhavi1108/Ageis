import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiGet, apiPost } from "../../services/apiClient";
import { qk } from "../../services/queryKeys";
import { usePollBaseMs } from "../useSettings";
import { taskRefetchInterval } from "../usePolling";
import type {
  Task,
  TaskCancelRequest,
  TaskCreate,
  TaskCreateResponse,
  TaskList,
  TaskTimeline,
} from "../../types/api";

export interface TaskListParams {
  repository_id?: string;
  state?: string;
  task_type?: string;
  limit?: number;
  offset?: number;
}

export function useTaskList(params: TaskListParams) {
  const query = {
    repository_id: params.repository_id,
    state: params.state,
    task_type: params.task_type,
    limit: params.limit ?? 25,
    offset: params.offset ?? 0,
  };
  return useQuery({
    queryKey: qk.tasks(query),
    queryFn: ({ signal }) => apiGet<TaskList>("/tasks", { signal, query }),
  });
}

export function useTask(id: string | undefined) {
  const baseMs = usePollBaseMs();
  return useQuery({
    queryKey: qk.task(id ?? ""),
    enabled: !!id,
    queryFn: ({ signal }) => apiGet<Task>(`/tasks/${id}`, { signal }),
    refetchInterval: (q) => taskRefetchInterval(q.state.data, baseMs),
    refetchIntervalInBackground: false,
  });
}

export function useTaskTimeline(id: string | undefined, taskState: string | undefined) {
  const baseMs = usePollBaseMs();
  return useQuery({
    queryKey: qk.taskTimeline(id ?? ""),
    enabled: !!id,
    queryFn: ({ signal }) => apiGet<TaskTimeline>(`/tasks/${id}/timeline`, { signal }),
    refetchInterval: () => taskRefetchInterval(taskState ? { state: taskState } : undefined, baseMs),
    refetchIntervalInBackground: false,
  });
}

export function useCreateTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: TaskCreate) => apiPost<TaskCreateResponse>("/tasks", body),
    onSuccess: (res) => {
      qc.setQueryData(qk.task(res.task.id), res.task);
      void qc.invalidateQueries({ queryKey: ["tasks"] });
    },
  });
}

export function useRunTask(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiPost<Task>(`/tasks/${id}/run`),
    onSuccess: (task) => {
      qc.setQueryData(qk.task(id), task);
      void qc.invalidateQueries({ queryKey: qk.taskTimeline(id) });
      void qc.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}

export function useCancelTask(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body?: TaskCancelRequest) => apiPost<Task>(`/tasks/${id}/cancel`, body),
    onSuccess: (task) => {
      qc.setQueryData(qk.task(id), task);
      void qc.invalidateQueries({ queryKey: qk.taskTimeline(id) });
    },
  });
}
