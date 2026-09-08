import { parseDiff, type FileData } from "react-diff-view";

export interface FileStat {
  key: string;
  path: string;
  oldPath: string;
  newPath: string;
  type: FileData["type"];
  additions: number;
  deletions: number;
}

export interface DiffStats {
  files: FileData[];
  fileStats: FileStat[];
  totalAdditions: number;
  totalDeletions: number;
}

export function parseUnifiedDiff(diffText: string): FileData[] {
  if (!diffText || !diffText.trim()) return [];
  try {
    return parseDiff(diffText);
  } catch {
    return [];
  }
}

export function computeDiffStats(diffText: string): DiffStats {
  const files = parseUnifiedDiff(diffText);
  let totalAdditions = 0;
  let totalDeletions = 0;
  const fileStats: FileStat[] = files.map((f, idx) => {
    let additions = 0;
    let deletions = 0;
    for (const hunk of f.hunks) {
      for (const change of hunk.changes) {
        if (change.type === "insert") additions += 1;
        else if (change.type === "delete") deletions += 1;
      }
    }
    totalAdditions += additions;
    totalDeletions += deletions;
    const path = f.type === "delete" ? f.oldPath : f.newPath;
    return {
      key: `${f.oldPath}→${f.newPath}#${idx}`,
      path,
      oldPath: f.oldPath,
      newPath: f.newPath,
      type: f.type,
      additions,
      deletions,
    };
  });
  return { files, fileStats, totalAdditions, totalDeletions };
}

/** Count of changed lines in a file, for the "collapse big files" guard. */
export function changedLineCount(file: FileData): number {
  let n = 0;
  for (const hunk of file.hunks) {
    for (const change of hunk.changes) {
      if (change.type !== "normal") n += 1;
    }
  }
  return n;
}
