// Hand-written types for the endpoints Phase 2 exposes. Later phases may
// replace this with a generated client from the backend's OpenAPI schema.

export interface HealthResponse {
  status: string;
}

export interface VersionResponse {
  version: string;
  git_sha: string | null;
}

// Mirrors backend/app/core/errors.py::ErrorEnvelope.
export interface ErrorEnvelope {
  code: string;
  message: string;
  details: Record<string, unknown> | null;
  evidence: unknown[] | null;
}
