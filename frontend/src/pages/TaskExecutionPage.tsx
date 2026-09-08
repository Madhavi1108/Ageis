import { useParams } from "react-router-dom";

import { PipelineView } from "../features/task-pipeline/PipelineView";

export function TaskExecutionPage() {
  const { taskId } = useParams();
  if (!taskId) return null;
  return <PipelineView taskId={taskId} />;
}
