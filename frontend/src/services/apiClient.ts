import type { ErrorEnvelope } from "../types/api";
import { getSettings } from "./settingsStore";

const ENV_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

/** Runtime base URL: Settings override wins, then the build-time env var. */
export function getBaseUrl(): string {
  const override = getSettings().apiBaseUrl?.trim();
  return (override && override.length > 0 ? override : ENV_BASE_URL).replace(/\/+$/, "");
}

export class ApiError extends Error {
  constructor(
    public readonly envelope: ErrorEnvelope,
    public readonly status: number,
  ) {
    super(envelope.message);
    this.name = "ApiError";
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }

  get isConflict(): boolean {
    return this.status === 409;
  }

  get isAuth(): boolean {
    return this.status === 401 || this.status === 403;
  }
}

function authHeaders(): Record<string, string> {
  const key = getSettings().apiKey?.trim();
  if (!key) return {};
  // The backend accepts either header; send both so it works regardless.
  return { Authorization: `Bearer ${key}`, "X-API-Key": key };
}

async function toEnvelope(response: Response): Promise<ErrorEnvelope> {
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    try {
      const body = (await response.json()) as Partial<ErrorEnvelope>;
      if (body && typeof body.code === "string" && typeof body.message === "string") {
        return {
          code: body.code,
          message: body.message,
          details: body.details ?? null,
          evidence: body.evidence ?? null,
        };
      }
      return {
        code: `HTTP_${response.status}`,
        message: response.statusText || "Request failed.",
        details: (body as Record<string, unknown>) ?? null,
        evidence: null,
      };
    } catch {
      // fall through
    }
  }
  return {
    code: `HTTP_${response.status}`,
    message: response.statusText || "Request failed.",
    details: null,
    evidence: null,
  };
}

export interface RequestOptions {
  signal?: AbortSignal;
  query?: Record<string, string | number | boolean | null | undefined>;
}

function networkError(cause: unknown): ApiError {
  return new ApiError(
    {
      code: "NETWORK_ERROR",
      message: "The backend is unreachable.",
      details: { cause: String(cause) },
      evidence: null,
    },
    0,
  );
}

function withQuery(path: string, query?: RequestOptions["query"]): string {
  if (!query) return path;
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v !== undefined && v !== null) qs.append(k, String(v));
  }
  const s = qs.toString();
  return s ? `${path}${path.includes("?") ? "&" : "?"}${s}` : path;
}

async function apiRequest<T>(
  method: "GET" | "POST" | "PATCH" | "DELETE",
  path: string,
  body?: unknown,
  opts?: RequestOptions,
): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json", ...authHeaders() };
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const url = `${getBaseUrl()}${withQuery(path, opts?.query)}`;
  const init: RequestInit = {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  };

  let response: Response;
  try {
    response = await fetch(url, { ...init, signal: opts?.signal });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    // Some environments (jsdom + a foreign AbortSignal) reject the signal itself;
    // retry once without it rather than failing the whole request.
    if (cause instanceof TypeError && /signal/i.test(cause.message)) {
      try {
        response = await fetch(url, init);
      } catch (retryCause) {
        throw networkError(retryCause);
      }
    } else {
      throw networkError(cause);
    }
  }

  if (!response.ok) {
    throw new ApiError(await toEnvelope(response), response.status);
  }

  if (response.status === 204 || response.headers.get("content-length") === "0") {
    return undefined as T;
  }
  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

export const apiGet = <T>(path: string, opts?: RequestOptions): Promise<T> =>
  apiRequest<T>("GET", path, undefined, opts);

export const apiPost = <T>(path: string, body?: unknown, opts?: RequestOptions): Promise<T> =>
  apiRequest<T>("POST", path, body, opts);

export const apiPatch = <T>(path: string, body?: unknown, opts?: RequestOptions): Promise<T> =>
  apiRequest<T>("PATCH", path, body, opts);

export const apiDelete = <T>(path: string, opts?: RequestOptions): Promise<T> =>
  apiRequest<T>("DELETE", path, undefined, opts);
