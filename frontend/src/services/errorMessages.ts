import { ApiError } from "./apiClient";
import type { ErrorEnvelope } from "../types/api";

/**
 * The backend's ErrorEnvelope.message is already human-readable, so the default
 * is to show it verbatim. This layer only improves a handful of synthetic /
 * transport / auth cases and adds a friendly prefix for "stage not run yet".
 */

const EXACT: Record<string, string> = {
  NETWORK_ERROR: "The backend is unreachable — check the API URL in System Settings.",
  VALIDATION_ERROR: "The request was rejected as invalid. Check the highlighted fields.",
  TASK_DUPLICATE: "An identical task already exists for this repository.",
  IMPLEMENTATION_PLAN_NOT_APPROVED:
    "The engineering plan must be validated as APPROVED before changes can be generated.",
  PR_NOT_VERIFIED: "A pull request can only be opened once the task is VERIFIED.",
  VERIFICATION_NOT_AWAITING_APPROVAL: "This task is not awaiting a human decision.",
  JOB_NOT_CANCELLABLE: "This job has already finished and cannot be cancelled.",
  AI_PROVIDER_NOT_CONFIGURED: "No AI provider is configured on the backend for this action.",
};

export function friendlyMessage(err: unknown): string {
  const env = toEnvelope(err);
  if (!env) {
    return err instanceof Error ? err.message : "Something went wrong.";
  }

  if (EXACT[env.code]) return EXACT[env.code];

  if (env.code.startsWith("HTTP_5") || env.code === "NETWORK_ERROR") {
    return "The backend is unreachable or errored — check the API URL in System Settings.";
  }
  if (env.code === "HTTP_401" || env.code === "HTTP_403") {
    return "This action needs an API key with the right role — add one in System Settings.";
  }
  if (/_NOT_FOUND$/.test(env.code) || /_MISSING$/.test(env.code) || /_INPUTS_MISSING$/.test(env.code)) {
    return env.message || "The requested data has not been produced for this task yet.";
  }
  return env.message || "Something went wrong.";
}

/**
 * "Stage not produced yet" vs a real error. Stage-precondition endpoints answer
 * 404 (nothing persisted) or 409 (a prior stage is missing) per the backend
 * route docstrings; anything else is a genuine error worth surfacing.
 */
export function isStageNotReady(err: unknown): boolean {
  if (!(err instanceof ApiError)) return false;
  return err.status === 404 || err.status === 409;
}

export function toEnvelope(err: unknown): ErrorEnvelope | null {
  if (err instanceof ApiError) return err.envelope;
  return null;
}

export function errorCode(err: unknown): string | null {
  return toEnvelope(err)?.code ?? null;
}

export function isAuthError(err: unknown): boolean {
  return err instanceof ApiError && err.isAuth;
}
