import type { ErrorEnvelope } from "../types/api";

const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public readonly envelope: ErrorEnvelope,
    public readonly status: number,
  ) {
    super(envelope.message);
    this.name = "ApiError";
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    const envelope = (await response.json()) as ErrorEnvelope;
    throw new ApiError(envelope, response.status);
  }
  return (await response.json()) as T;
}
