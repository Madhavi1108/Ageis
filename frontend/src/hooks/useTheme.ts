import { useEffect } from "react";

import { useSettings } from "./useSettings";

function apply(dark: boolean): void {
  document.documentElement.classList.toggle("dark", dark);
}

function prefersDark(): boolean {
  try {
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  } catch {
    return false;
  }
}

/** Resolves the theme preference to a concrete light/dark and keeps <html> in sync. */
export function useTheme(): {
  preference: "light" | "dark" | "system";
  resolved: "light" | "dark";
  setPreference: (p: "light" | "dark" | "system") => void;
  toggle: () => void;
} {
  const { settings, update } = useSettings();
  const resolved: "light" | "dark" =
    settings.theme === "system" ? (prefersDark() ? "dark" : "light") : settings.theme;

  useEffect(() => {
    apply(resolved === "dark");
  }, [resolved]);

  useEffect(() => {
    if (settings.theme !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => apply(mq.matches);
    mq.addEventListener?.("change", handler);
    return () => mq.removeEventListener?.("change", handler);
  }, [settings.theme]);

  return {
    preference: settings.theme,
    resolved,
    setPreference: (p) => update({ theme: p }),
    toggle: () => update({ theme: resolved === "dark" ? "light" : "dark" }),
  };
}
