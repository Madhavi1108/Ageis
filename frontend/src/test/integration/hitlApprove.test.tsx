import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { VerificationResultPage } from "../../pages/VerificationResultPage";
import { makeTask, makeVerification, TASK_ID } from "../fixtures";
import { server } from "../msw/server";
import { renderWithProviders } from "../utils/renderWithProviders";

const BASE = "http://localhost:8000";

describe("HITL approve flow", () => {
  it("submits an APPROVE decision with the right body and reflects the new state", async () => {
    let posted: unknown = null;
    server.use(
      http.get(`${BASE}/tasks/:id`, () => HttpResponse.json(makeTask({ state: "AWAITING_APPROVAL" }))),
      http.get(`${BASE}/tasks/:id/verification`, () =>
        HttpResponse.json(makeVerification({ verdict: "PARTIAL", resulting_state: "AWAITING_APPROVAL" })),
      ),
      http.post(`${BASE}/tasks/:id/verification/decision`, async ({ request }) => {
        posted = await request.json();
        const decided = makeVerification({
          verdict: "VERIFIED",
          resulting_state: "COMPLETED",
          decision: {
            decision: "APPROVE",
            reason: "ship it",
            actor: "Reviewer",
            decided_at: "2026-09-08T11:00:00Z",
          },
        });
        // subsequent GETs reflect the recorded decision (as the real backend does)
        server.use(
          http.get(`${BASE}/tasks/:id`, () => HttpResponse.json(makeTask({ state: "COMPLETED" }))),
          http.get(`${BASE}/tasks/:id/verification`, () => HttpResponse.json(decided)),
        );
        return HttpResponse.json(decided);
      }),
    );

    renderWithProviders(<VerificationResultPage />, {
      route: `/tasks/${TASK_ID}/verification`,
      path: "/tasks/:taskId/verification",
    });

    const approve = await screen.findByRole("button", { name: "Approve" });
    await userEvent.click(approve);

    await userEvent.type(screen.getByLabelText(/Your name/i), "Reviewer");
    await userEvent.type(screen.getByLabelText(/Reason/i), "ship it");
    await userEvent.click(screen.getByRole("button", { name: /Confirm approve/i }));

    await waitFor(() =>
      expect(posted).toEqual({ decision: "APPROVE", reason: "ship it", actor: "Reviewer" }),
    );

    // the recorded decision now renders
    expect(await screen.findByText(/Human decision \(recorded\)/i)).toBeInTheDocument();
  });

  it("shows a friendly auth message when the decision endpoint returns 403", async () => {
    server.use(
      http.get(`${BASE}/tasks/:id`, () => HttpResponse.json(makeTask({ state: "AWAITING_APPROVAL" }))),
      http.get(`${BASE}/tasks/:id/verification`, () =>
        HttpResponse.json(makeVerification({ verdict: "PARTIAL", resulting_state: "AWAITING_APPROVAL" })),
      ),
      http.post(`${BASE}/tasks/:id/verification/decision`, () =>
        HttpResponse.json(
          { code: "HTTP_403", message: "forbidden", details: null, evidence: null },
          { status: 403 },
        ),
      ),
    );

    renderWithProviders(<VerificationResultPage />, {
      route: `/tasks/${TASK_ID}/verification`,
      path: "/tasks/:taskId/verification",
    });

    await userEvent.click(await screen.findByRole("button", { name: "Reject" }));
    await userEvent.type(screen.getByLabelText(/Your name/i), "Reviewer");
    await userEvent.type(screen.getByLabelText(/Reason/i), "no");
    await userEvent.click(screen.getByRole("button", { name: /Confirm reject/i }));

    expect(await screen.findByText(/needs an API key with the right role/i)).toBeInTheDocument();
  });
});
