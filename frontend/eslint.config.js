import js from "@eslint/js";
import tseslint from "@typescript-eslint/eslint-plugin";
import tsParser from "@typescript-eslint/parser";
import jsxA11y from "eslint-plugin-jsx-a11y";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";

const browserGlobals = {
  document: "readonly",
  window: "readonly",
  fetch: "readonly",
  console: "readonly",
  navigator: "readonly",
  localStorage: "readonly",
  setTimeout: "readonly",
  clearTimeout: "readonly",
  setInterval: "readonly",
  clearInterval: "readonly",
  requestAnimationFrame: "readonly",
  queueMicrotask: "readonly",
  URL: "readonly",
  URLSearchParams: "readonly",
  Blob: "readonly",
  FormData: "readonly",
  AbortController: "readonly",
  EventSource: "readonly",
  MediaQueryList: "readonly",
  ResizeObserver: "readonly",
  IntersectionObserver: "readonly",
  HTMLElement: "readonly",
  HTMLInputElement: "readonly",
  HTMLTextAreaElement: "readonly",
  HTMLAnchorElement: "readonly",
  Element: "readonly",
  Node: "readonly",
  getComputedStyle: "readonly",
  ImportMetaEnv: "readonly",
};

const testGlobals = {
  describe: "readonly",
  it: "readonly",
  test: "readonly",
  expect: "readonly",
  vi: "readonly",
  beforeAll: "readonly",
  afterAll: "readonly",
  beforeEach: "readonly",
  afterEach: "readonly",
};

export default [
  { ignores: ["dist", "src/types/api-generated.ts", "coverage", "playwright-report"] },
  js.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      parser: tsParser,
      ecmaVersion: 2022,
      sourceType: "module",
      globals: browserGlobals,
    },
    plugins: {
      "@typescript-eslint": tseslint,
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
      "jsx-a11y": jsxA11y,
    },
    rules: {
      ...tseslint.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      ...jsxA11y.flatConfigs.recommended.rules,
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
      // TypeScript's own checker handles undefined identifiers (incl. DOM lib
      // types and the JSX namespace); the core rule produces false positives.
      "no-undef": "off",
    },
  },
  {
    files: ["src/**/*.{test,spec}.{ts,tsx}", "src/test/**/*.{ts,tsx}"],
    languageOptions: {
      globals: { ...browserGlobals, ...testGlobals, global: "readonly", process: "readonly" },
    },
    rules: {
      "@typescript-eslint/no-non-null-assertion": "off",
      "react-refresh/only-export-components": "off",
    },
  },
  {
    files: ["e2e/**/*.{ts,tsx}"],
    languageOptions: {
      globals: { ...testGlobals, process: "readonly", console: "readonly" },
    },
  },
  {
    // context providers that also export their hook — intentional co-location
    files: ["src/hooks/useSettings.tsx", "src/components/feedback/Toast.tsx"],
    rules: { "react-refresh/only-export-components": "off" },
  },
  {
    files: ["*.config.{ts,js}"],
    languageOptions: { globals: { process: "readonly" } },
  },
];
