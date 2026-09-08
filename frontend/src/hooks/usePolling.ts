import { TERMINAL_STATES } from "../types/pipeline";

/**
 * Refetch interval for the task + its timeline, driven by task state:
 *  - no task yet            -> keep trying at the base cadence
 *  - terminal state         -> stop
 *  - AWAITING_APPROVAL      -> slow poll (waiting on a human; catch another actor)
 *  - any active state       -> base cadence
 */
export function taskRefetchInterval(
  task: { state: string } | undefined,
  baseMs: number,
): number | false {
  if (!Number.isFinite(baseMs) || baseMs <= 0) return false; // "Live" toggle off
  if (!task) return baseMs;
  if (TERMINAL_STATES.has(task.state)) return false;
  if (task.state === "AWAITING_APPROVAL") return baseMs * 4;
  return baseMs;
}
