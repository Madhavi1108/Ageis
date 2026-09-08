import { useQuery } from "@tanstack/react-query";

import { apiGet } from "../../services/apiClient";
import { qk, type StageKey } from "../../services/queryKeys";
import type {
  EngineeringMemoryOut,
  EngineeringPlan,
  FailureAnalysis,
  ImpactAnalysis,
  ImplementationResult,
  IssueCodeMapping,
  PatchConfidence,
  PatchRiskAssessment,
  PullRequestOut,
  RegressionResult,
  RepairResult,
  ReviewReport,
  TestExecution,
  TestGeneration,
  VerificationResult,
} from "../../types/api";

interface Opts {
  enabled?: boolean;
}

function useStageQuery<T>(
  taskId: string | undefined,
  stage: StageKey,
  path: string,
  opts?: Opts,
) {
  return useQuery({
    queryKey: qk.taskStage(taskId ?? "", stage),
    enabled: !!taskId && (opts?.enabled ?? true),
    retry: false,
    queryFn: ({ signal }) => apiGet<T>(`/tasks/${taskId}${path}`, { signal }),
  });
}

export const usePlan = (id: string | undefined, o?: Opts) =>
  useStageQuery<EngineeringPlan>(id, "plan", "/plan", o);

export const useMapping = (id: string | undefined, o?: Opts) =>
  useStageQuery<IssueCodeMapping>(id, "mapping", "/mapping", o);

export const useImpact = (id: string | undefined, o?: Opts) =>
  useStageQuery<ImpactAnalysis>(id, "impact", "/impact", o);

export const useChanges = (id: string | undefined, o?: Opts) =>
  useStageQuery<ImplementationResult>(id, "changes", "/changes", o);

export const useTests = (id: string | undefined, o?: Opts) =>
  useStageQuery<TestGeneration>(id, "tests", "/tests", o);

export const useExecutions = (id: string | undefined, o?: Opts) =>
  useStageQuery<TestExecution[]>(id, "executions", "/executions", o);

export const useFailures = (id: string | undefined, o?: Opts) =>
  useStageQuery<FailureAnalysis>(id, "failures", "/failures", o);

export const useRepairs = (id: string | undefined, o?: Opts) =>
  useStageQuery<RepairResult>(id, "repairs", "/repairs", o);

export const useRegression = (id: string | undefined, o?: Opts) =>
  useStageQuery<RegressionResult>(id, "regression", "/regression", o);

export const useReview = (id: string | undefined, o?: Opts) =>
  useStageQuery<ReviewReport>(id, "review", "/review", o);

export const useRisk = (id: string | undefined, o?: Opts) =>
  useStageQuery<PatchRiskAssessment>(id, "risk", "/risk", o);

export const useConfidence = (id: string | undefined, o?: Opts) =>
  useStageQuery<PatchConfidence>(id, "confidence", "/confidence", o);

export const useVerification = (id: string | undefined, o?: Opts) =>
  useStageQuery<VerificationResult>(id, "verification", "/verification", o);

export const usePr = (id: string | undefined, o?: Opts) =>
  useStageQuery<PullRequestOut>(id, "pr", "/pr", o);

export const useTaskMemory = (id: string | undefined, o?: Opts) =>
  useStageQuery<EngineeringMemoryOut>(id, "memory", "/memory", o);
