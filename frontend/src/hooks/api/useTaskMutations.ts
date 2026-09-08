import { useMutation, useQueryClient } from "@tanstack/react-query";

import { apiPost } from "../../services/apiClient";
import { qk } from "../../services/queryKeys";
import type {
  EngineeringPlan,
  ImplementationResult,
  PullRequestCreateRequest,
  PullRequestOut,
  TestExecution,
  VerificationDecisionRequest,
  VerificationResult,
} from "../../types/api";

function useTaskInvalidator(taskId: string) {
  const qc = useQueryClient();
  return () => {
    void qc.invalidateQueries({ queryKey: qk.task(taskId) });
    void qc.invalidateQueries({ queryKey: qk.taskTimeline(taskId) });
  };
}

export function useRegeneratePlan(taskId: string) {
  const qc = useQueryClient();
  const invalidate = useTaskInvalidator(taskId);
  return useMutation({
    mutationFn: () => apiPost<EngineeringPlan>(`/tasks/${taskId}/plan`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: qk.taskStage(taskId, "plan") });
      invalidate();
    },
  });
}

export function useValidatePlan(taskId: string) {
  const qc = useQueryClient();
  const invalidate = useTaskInvalidator(taskId);
  return useMutation({
    mutationFn: () => apiPost<EngineeringPlan>(`/tasks/${taskId}/plan/validate`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: qk.taskStage(taskId, "plan") });
      invalidate();
    },
  });
}

export function useRegenerateChanges(taskId: string) {
  const qc = useQueryClient();
  const invalidate = useTaskInvalidator(taskId);
  return useMutation({
    mutationFn: () => apiPost<ImplementationResult>(`/tasks/${taskId}/changes`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: qk.taskStage(taskId, "changes") });
      invalidate();
    },
  });
}

export function useRerunTests(taskId: string) {
  const qc = useQueryClient();
  const invalidate = useTaskInvalidator(taskId);
  return useMutation({
    mutationFn: () => apiPost<TestExecution>(`/tasks/${taskId}/executions`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: qk.taskStage(taskId, "executions") });
      invalidate();
    },
  });
}

export function useCreatePr(taskId: string) {
  const qc = useQueryClient();
  const invalidate = useTaskInvalidator(taskId);
  return useMutation({
    mutationFn: (body?: PullRequestCreateRequest) =>
      apiPost<PullRequestOut>(`/tasks/${taskId}/pr`, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: qk.taskStage(taskId, "pr") });
      invalidate();
    },
  });
}

export function useVerificationDecision(taskId: string) {
  const qc = useQueryClient();
  const invalidate = useTaskInvalidator(taskId);
  return useMutation({
    mutationFn: (body: VerificationDecisionRequest) =>
      apiPost<VerificationResult>(`/tasks/${taskId}/verification/decision`, body),
    onSuccess: (result) => {
      // the response body IS the new verification row — seed the cache with it
      qc.setQueryData(qk.taskStage(taskId, "verification"), result);
      void qc.invalidateQueries({ queryKey: qk.taskStage(taskId, "verification") });
      void qc.invalidateQueries({ queryKey: qk.taskStage(taskId, "pr") });
      invalidate();
    },
  });
}
