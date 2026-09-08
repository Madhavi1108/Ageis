import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import {
  getSettings,
  setSettings,
  subscribeSettings,
  type AppSettings,
} from "../services/settingsStore";

interface SettingsContextValue {
  settings: AppSettings;
  update: (patch: Partial<AppSettings>) => void;
}

const SettingsContext = createContext<SettingsContextValue | null>(null);

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setLocal] = useState<AppSettings>(() => getSettings());

  useEffect(() => subscribeSettings(setLocal), []);

  const value = useMemo<SettingsContextValue>(
    () => ({ settings, update: (patch) => setLocal(setSettings(patch)) }),
    [settings],
  );

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

export function useSettings(): SettingsContextValue {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error("useSettings must be used within <SettingsProvider>");
  return ctx;
}

/** Effective poll cadence in ms, or 0 when the "Live" toggle is off. */
export function usePollBaseMs(): number {
  const { settings } = useSettings();
  return settings.livePolling ? settings.pollBaseMs : 0;
}
