import { useState } from "react";

import { useVerificationDecision } from "../../hooks/api/useTaskMutations";
import { useVerification } from "../../hooks/api/useTaskStages";
import { useSettings } from "../../hooks/useSettings";
import { useToast } from "../../components/feedback/Toast";
import { ErrorEnvelopeAlert } from "../../components/feedback/ErrorEnvelopeAlert";
import { Button } from "../../components/primitives/Button";
import { Card, CardBody, CardHeader } from "../../components/primitives/Card";
import { Dialog, DialogClose } from "../../components/primitives/Dialog";
import { TextArea, TextField } from "../../components/primitives/Field";
import { absoluteTime } from "../../lib/format";

export function DecisionControls({ taskId }: { taskId: string }) {
  const { settings } = useSettings();
  const { notify } = useToast();
  const verification = useVerification(taskId);
  const decide = useVerificationDecision(taskId);

  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState<"APPROVE" | "REJECT">("APPROVE");
  const [reason, setReason] = useState("");
  const [actor, setActor] = useState(settings.actorName ?? "");

  const existing = verification.data?.decision;
  if (existing) {
    return (
      <Card>
        <CardHeader title="Human decision (recorded)" />
        <CardBody className="text-sm">
          <p>
            <strong>{existing.decision}</strong> by {existing.actor} ·{" "}
            {absoluteTime(existing.decided_at)}
          </p>
          <p className="mt-1 text-muted">{existing.reason}</p>
        </CardBody>
      </Card>
    );
  }

  function openFor(k: "APPROVE" | "REJECT") {
    setKind(k);
    setReason("");
    setActor(settings.actorName ?? "");
    setOpen(true);
  }

  return (
    <Card>
      <CardHeader
        title="This task is awaiting a human decision"
        subtitle="Verification returned PARTIAL — approve to complete, reject to fail."
      />
      <CardBody>
        <div className="flex gap-2">
          <Button variant="primary" onClick={() => openFor("APPROVE")}>
            Approve
          </Button>
          <Button variant="danger" onClick={() => openFor("REJECT")}>
            Reject
          </Button>
        </div>
        {decide.isError ? <ErrorEnvelopeAlert error={decide.error} className="mt-2" /> : null}

        <Dialog
          open={open}
          onOpenChange={setOpen}
          title={kind === "APPROVE" ? "Approve this change" : "Reject this change"}
          description="Recorded on the verification row with your name and reason."
        >
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              decide.mutate(
                { decision: kind, reason: reason.trim(), actor: actor.trim() },
                {
                  onSuccess: (res) => {
                    setOpen(false);
                    notify(`Decision recorded — task is now ${res.resulting_state}`, "success");
                  },
                },
              );
            }}
          >
            <TextField
              label="Your name"
              required
              maxLength={255}
              value={actor}
              onChange={(e) => setActor(e.target.value)}
            />
            <TextArea
              label="Reason"
              required
              minLength={1}
              maxLength={2000}
              rows={4}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
            <div className="flex justify-end gap-2">
              <DialogClose asChild>
                <Button type="button" variant="ghost">
                  Cancel
                </Button>
              </DialogClose>
              <Button
                type="submit"
                variant={kind === "APPROVE" ? "primary" : "danger"}
                disabled={decide.isPending || !reason.trim() || !actor.trim()}
              >
                {decide.isPending ? "Submitting…" : `Confirm ${kind.toLowerCase()}`}
              </Button>
            </div>
          </form>
        </Dialog>
      </CardBody>
    </Card>
  );
}
