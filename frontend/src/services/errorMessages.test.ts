import { describe, expect, it } from "vitest";

import { ApiError } from "./apiClient";
import { errorCode, friendlyMessage, isStageNotReady } from "./errorMessages";

function err(code: string, status: number, message = "backend message") {
  return new ApiError({ code, message, details: null, evidence: null }, status);
}

describe("errorMessages", () => {
  it("maps a known code to friendly text", () => {
    expect(friendlyMessage(err("TASK_DUPLICATE", 409))).toMatch(/already exists/i);
  });

  it("falls back to the envelope message for an unknown code", () => {
    expect(friendlyMessage(err("SOMETHING_WEIRD", 400, "the backend said this"))).toBe(
      "the backend said this",
    );
  });

  it("uses a generic message when there is no envelope", () => {
    expect(friendlyMessage(new Error(""))).toBe("");
    expect(friendlyMessage("nope")).toBe("Something went wrong.");
  });

  it("special-cases 401/403 and 5xx", () => {
    expect(friendlyMessage(err("HTTP_403", 403))).toMatch(/API key/i);
    expect(friendlyMessage(err("HTTP_502", 502))).toMatch(/unreachable/i);
  });

  it("isStageNotReady is true for 404 and 409", () => {
    expect(isStageNotReady(err("PLAN_NOT_FOUND", 404))).toBe(true);
    expect(isStageNotReady(err("TASK_INVALID_STATE", 409))).toBe(true);
    expect(isStageNotReady(err("VALIDATION_ERROR", 422))).toBe(false);
    expect(isStageNotReady(new Error("x"))).toBe(false);
  });

  it("errorCode extracts the code", () => {
    expect(errorCode(err("PLAN_NOT_FOUND", 404))).toBe("PLAN_NOT_FOUND");
    expect(errorCode(new Error("x"))).toBeNull();
  });
});
