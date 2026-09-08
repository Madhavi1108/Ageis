// Curated API surface. Types come from src/types/api-generated.ts (produced by
// `npm run gen:api` from openapi/openapi.snapshot.json). Refresh after backend
// API changes; there is no CI drift gate (documented Phase 22 open item).

import type { components } from "./api-generated";

type S = components["schemas"];

// --- repositories -------------------------------------------------------------
export type RepositoryRef = S["RepositoryRef"];
export type RepositoryCreateRequest = S["RepositoryCreateRequest"];
export type IngestRequest = S["IngestRequest"];
export type IngestResult = S["IngestResult"];
export type RepositoryHealthProfile = S["RepositoryHealthProfile"];
export type RiskyModule = S["RiskyModule"];
export type GitContext = S["GitContext"];
export type CommitInfo = S["CommitInfo"];
export type ChurnEntry = S["ChurnEntry"];
export type BlameHunk = S["BlameHunk"];

// --- tasks ------------------------------------------------------------------
export type Task = S["Task"];
export type TaskList = S["TaskList"];
export type TaskCreate = S["TaskCreate"];
export type TaskCreateResponse = S["TaskCreateResponse"];
export type TaskCancelRequest = S["TaskCancelRequest"];
export type NormalizationInfo = S["NormalizationInfo"];
export type TaskTimeline = S["TaskTimeline"];
export type TimelineEntry = S["TimelineEntry"];
export type IssueAnalysisInput = S["IssueAnalysisInput"];

// --- jobs ------------------------------------------------------------------
export type JobView = S["JobView"];
export type JobList = S["JobList"];

// --- analysis / mapping / impact -----------------------------------------
export type RepositoryAnalysisResult = S["RepositoryAnalysisResult"];
export type IssueCodeMapping = S["IssueCodeMapping"];
export type MappingCandidate = S["MappingCandidate"];
export type ImpactAnalysis = S["ImpactAnalysis"];
export type SymbolCallers = S["SymbolCallers"];
export type RegressionArea = S["RegressionArea"];
export type MapRequest = S["MapRequest"];

// --- graph ------------------------------------------------------------------
export type CodeGraphSummary = S["CodeGraphSummary"];
export type SubgraphResult = S["SubgraphResult"];
export type NodeDetail = S["NodeDetail"];
export type NodeRef = S["NodeRef"];
export type EdgeRef = S["EdgeRef"];

// --- plan ------------------------------------------------------------------
export type EngineeringPlan = S["EngineeringPlan"];
export type PlanStep = S["PlanStep"];
export type PlanValidation = S["PlanValidation"];

// --- implementation -------------------------------------------------------
export type ImplementationResult = S["ImplementationResult"];
export type EditOp = S["EditOp"];
export type PatchSummary = S["PatchSummary"];

// --- testing / execution ------------------------------------------------
export type TestGeneration = S["TestGeneration"];
export type TestCase = S["TestCase"];
export type TestExecution = S["TestExecution"];
export type TestOutcome = S["TestOutcome"];

// --- debugging ----------------------------------------------------------
export type FailureAnalysis = S["FailureAnalysis"];
export type FailureRecord = S["FailureRecord"];
export type Frame = S["Frame"];
export type RepairResult = S["RepairResult"];
export type RepairAttemptView = S["RepairAttemptView"];
export type SafeStop = S["SafeStop"];

// --- regression -------------------------------------------------------
export type RegressionResult = S["RegressionResult"];
export type RegressionPlan = S["RegressionPlan"];
export type ClassifiedTest = S["ClassifiedTest"];

// --- review ---------------------------------------------------------
export type ReviewReport = S["ReviewReport"];
export type ReviewFinding = S["ReviewFinding"];

// --- scoring ------------------------------------------------------
export type PatchConfidence = S["PatchConfidence"];
export type PatchRiskAssessment = S["PatchRiskAssessment"];
export type SignalContribution = S["SignalContribution"];

// --- verification -----------------------------------------------
export type VerificationResult = S["VerificationResult"];
export type CriterionResult = S["CriterionResult"];
export type PlanAlignment = S["PlanAlignment"];
export type ExplainabilityTrace = S["ExplainabilityTrace"];
export type VerificationDecision = S["VerificationDecision"];
export type VerificationDecisionRequest = S["VerificationDecisionRequest"];

// --- github -----------------------------------------------------
export type GitHubRepoInfo = S["GitHubRepoInfo"];
export type GitHubIssueInfo = S["GitHubIssueInfo"];
export type IssueRef = S["IssueRef"];
export type PullRequestOut = S["PullRequestOut"];
export type PullRequestCreateRequest = S["PullRequestCreateRequest"];

// --- memory ---------------------------------------------------
export type EngineeringMemoryOut = S["EngineeringMemoryOut"];
export type MemoryHit = S["MemoryHit"];
export type MemorySearchRequest = S["MemorySearchRequest"];

// --- shared -----------------------------------------------
export type Evidence = S["Evidence"];
export type Confidence = S["Confidence"];

// --- health (not always a named component) ---------------------
export interface HealthResponse {
  status: string;
}
export interface VersionResponse {
  version: string;
  git_sha: string | null;
}

// Mirrors backend/app/core/errors.py::ErrorEnvelope. Kept hand-written because
// FastAPI error bodies are not always a named OpenAPI component.
export interface ErrorEnvelope {
  code: string;
  message: string;
  details: Record<string, unknown> | null;
  evidence: unknown[] | null;
}
