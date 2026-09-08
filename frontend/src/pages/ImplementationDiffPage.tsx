import { useParams } from "react-router-dom";

import {
  useChanges,
  useConfidence,
  useReview,
  useRisk,
  useTests,
} from "../hooks/api/useTaskStages";
import { useTask } from "../hooks/api/useTasks";
import { DiffViewer } from "../features/diff/DiffViewer";
import { DecisionControls } from "../features/verification/DecisionControls";
import { EmptyState } from "../components/feedback/EmptyState";
import { LoadingBlock } from "../components/feedback/LoadingBlock";
import { ErrorEnvelopeAlert } from "../components/feedback/ErrorEnvelopeAlert";
import { isStageNotReady } from "../services/errorMessages";

export function ImplementationDiffPage() {
  const { taskId = "" } = useParams();
  const task = useTask(taskId);
  const changes = useChanges(taskId);
  const review = useReview(taskId);
  const risk = useRisk(taskId);
  const confidence = useConfidence(taskId);
  const tests = useTests(taskId);

  if (changes.isLoading) return <LoadingBlock rows={6} />;
  if (changes.isError && isStageNotReady(changes.error)) {
    return <EmptyState title="No implementation generated yet." hint="The implement stage has not produced a patch." />;
  }
  if (changes.isError) return <ErrorEnvelopeAlert error={changes.error} />;
  if (!changes.data) return null;

  const awaiting = task.data?.state === "AWAITING_APPROVAL";

  return (
    <DiffViewer
      implementation={changes.data}
      review={review.data}
      risk={risk.data}
      confidence={confidence.data}
      tests={tests.data}
      decisionSlot={awaiting ? <DecisionControls taskId={taskId} /> : undefined}
    />
  );
}
