import { afterEach, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";

import { server } from "../test/msw/server";
import { _resetSettingsCache, setSettings } from "./settingsStore";
import { ApiError, apiGet, apiPost, getBaseUrl } from "./apiClient";

const BASE = "http://localhost:8000";

afterEach(() => {
  try {
    localStorage.clear();
  } catch {
    /* ignore */
  }
  _resetSettingsCache();
});

describe("apiClient", () => {
  it("uses the env base URL by default and the Settings override when set", () => {
    expect(getBaseUrl()).toBe(BASE);
    setSettings({ apiBaseUrl: "http://example.test:9000/" });
    expect(getBaseUrl()).toBe("http://example.test:9000");
  });

  it("injects Authorization + X-API-Key only when a key is set", async () => {
    let seen: Headers | null = null;
    server.use(
      http.get(`${BASE}/probe`, ({ request }) => {
        seen = request.headers;
        return HttpResponse.json({ ok: true });
      }),
    );

    await apiGet("/probe");
    expect(seen!.get("authorization")).toBeNull();
    expect(seen!.get("x-api-key")).toBeNull();

    setSettings({ apiKey: "secret-key" });
    await apiGet("/probe");
    expect(seen!.get("authorization")).toBe("Bearer secret-key");
    expect(seen!.get("x-api-key")).toBe("secret-key");
  });

  it("sends Content-Type only when there is a body", async () => {
    const cts: (string | null)[] = [];
    server.use(
      http.post(`${BASE}/probe`, ({ request }) => {
        cts.push(request.headers.get("content-type"));
        return HttpResponse.json({ ok: true });
      }),
    );
    await apiPost("/probe");
    await apiPost("/probe", { a: 1 });
    expect(cts[0]).toBeNull();
    expect(cts[1]).toContain("application/json");
  });

  it("throws ApiError with the parsed envelope on a JSON error", async () => {
    server.use(
      http.get(`${BASE}/probe`, () =>
        HttpResponse.json(
          { code: "TASK_NOT_FOUND", message: "no such task", details: null, evidence: null },
          { status: 404 },
        ),
      ),
    );
    await expect(apiGet("/probe")).rejects.toMatchObject({
      status: 404,
      envelope: { code: "TASK_NOT_FOUND" },
    });
  });

  it("synthesizes an envelope for a non-JSON 500", async () => {
    server.use(
      http.get(`${BASE}/probe`, () => new HttpResponse("boom", { status: 500 })),
    );
    try {
      await apiGet("/probe");
      throw new Error("should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError);
      expect((e as ApiError).envelope.code).toBe("HTTP_500");
    }
  });

  it("returns undefined for a 204", async () => {
    server.use(http.post(`${BASE}/probe`, () => new HttpResponse(null, { status: 204 })));
    await expect(apiPost("/probe")).resolves.toBeUndefined();
  });

  it("still completes the request when the runtime rejects the AbortSignal (jsdom/undici realm mismatch)", async () => {
    // In a real browser the signal is valid and cancellation works; this asserts
    // the defensive retry-without-signal fallback so a foreign signal can't make
    // every request fail.
    server.use(http.get(`${BASE}/slow`, () => HttpResponse.json({ ok: true })));
    const ac = new AbortController();
    await expect(apiGet("/slow", { signal: ac.signal })).resolves.toEqual({ ok: true });
  });
});
