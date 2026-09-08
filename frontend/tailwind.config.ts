import type { Config } from "tailwindcss";

/**
 * Class-based dark mode: `useTheme` toggles `.dark` on <html>. Semantic tokens
 * resolve to CSS variables defined in src/index.css so both themes share one
 * scale.
 */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: "rgb(var(--bg) / <alpha-value>)",
        surface: "rgb(var(--surface) / <alpha-value>)",
        "surface-2": "rgb(var(--surface-2) / <alpha-value>)",
        border: "rgb(var(--border) / <alpha-value>)",
        fg: "rgb(var(--fg) / <alpha-value>)",
        muted: "rgb(var(--muted) / <alpha-value>)",
        accent: "rgb(var(--accent) / <alpha-value>)",
        "accent-fg": "rgb(var(--accent-fg) / <alpha-value>)",
        // pipeline stage + task-state semantics
        pending: "rgb(var(--pending) / <alpha-value>)",
        active: "rgb(var(--active) / <alpha-value>)",
        done: "rgb(var(--done) / <alpha-value>)",
        failed: "rgb(var(--failed) / <alpha-value>)",
        skipped: "rgb(var(--skipped) / <alpha-value>)",
        awaiting: "rgb(var(--awaiting) / <alpha-value>)",
        // review / risk severity
        "sev-critical": "rgb(var(--sev-critical) / <alpha-value>)",
        "sev-high": "rgb(var(--sev-high) / <alpha-value>)",
        "sev-medium": "rgb(var(--sev-medium) / <alpha-value>)",
        "sev-low": "rgb(var(--sev-low) / <alpha-value>)",
        "sev-info": "rgb(var(--sev-info) / <alpha-value>)",
      },
      fontFamily: {
        sans: ['system-ui', '-apple-system', '"Segoe UI"', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
} satisfies Config;
