// localStorage-backed client settings. No React here so non-component code
// (apiClient, tests) can read/write it. Every access is guarded — private
// windows and blocked site-data both throw or return null.

export type ThemePreference = "light" | "dark" | "system";

export interface AppSettings {
  apiBaseUrl: string | null;
  apiKey: string | null;
  actorName: string | null;
  theme: ThemePreference;
  pollBaseMs: number;
  livePolling: boolean;
  graphNodeCap: number;
  knownRepoIds: string[];
}

const KEY = "aegis.settings.v1";

export const DEFAULT_SETTINGS: AppSettings = {
  apiBaseUrl: null,
  apiKey: null,
  actorName: null,
  theme: "system",
  pollBaseMs: 2000,
  livePolling: true,
  graphNodeCap: 300,
  knownRepoIds: [],
};

type Listener = (s: AppSettings) => void;
const listeners = new Set<Listener>();
let cache: AppSettings | null = null;

function read(): AppSettings {
  if (cache) return cache;
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<AppSettings>;
      cache = { ...DEFAULT_SETTINGS, ...parsed };
      return cache;
    }
  } catch {
    // ignore — fall through to defaults
  }
  cache = { ...DEFAULT_SETTINGS };
  return cache;
}

function write(next: AppSettings): void {
  cache = next;
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    // best-effort — the in-memory cache still serves this session
  }
  for (const l of listeners) l(next);
}

export function getSettings(): AppSettings {
  return read();
}

export function setSettings(patch: Partial<AppSettings>): AppSettings {
  const next = { ...read(), ...patch };
  write(next);
  return next;
}

export function subscribeSettings(fn: Listener): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function rememberRepoId(id: string): void {
  const s = read();
  if (!s.knownRepoIds.includes(id)) {
    setSettings({ knownRepoIds: [...s.knownRepoIds, id] });
  }
}

export function forgetRepoId(id: string): void {
  const s = read();
  setSettings({ knownRepoIds: s.knownRepoIds.filter((x) => x !== id) });
}

// test seam
export function _resetSettingsCache(): void {
  cache = null;
}
