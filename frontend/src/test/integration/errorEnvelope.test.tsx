import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";

import { CodeImpactPage } from "../../pages/CodeImpactPage";
import { TASK_ID } from "../fixtures";
import { server } from "../msw/server";
import { renderWithProviders } from "../utils/renderWithProviders";

const BASE = "http://localhost:8000";

describe("error envelope surfacing", () => {
  it("renders a friendly message + code tag for a real (non-precondition) error", async () => {
    server.use(
      http.get(`${BASE}/tasks/:id/impact`, () =>
        HttpResponse.json(
          { code: "IMPACT_MAPPING_MISSING", message: "mapping missing", details: { need: "mapping" }, evidence: null },
          { status: 500 },
        ),
      ),
    );

    renderWithProviders(<CodeImpactPage />, {
      route: `/tasks/${TASK_ID}/impact`,
      path: "/tasks/:taskId/impact",
    });

    expect(await screen.findByText("mapping missing")).toBeInTheDocument();
    expect(screen.getByText("IMPACT_MAPPING_MISSING")).toBeInTheDocument();
  });

  it("renders a 'not produced yet' empty state (not an error) for a 404 stage", async () => {
    server.use(
      http.get(`${BASE}/tasks/:id/impact`, () =>
        HttpResponse.json(
          { code: "IMPACT_TASK_NOT_FOUND", message: "no impact", details: null, evidence: null },
          { status: 404 },
        ),
      ),
    );

    renderWithProviders(<CodeImpactPage />, {
      route: `/tasks/${TASK_ID}/impact`,
      path: "/tasks/:taskId/impact",
    });

    expect(await screen.findByText(/No impact analysis produced yet/i)).toBeInTheDocument();
  });
});
