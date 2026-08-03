import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

import { createRequire } from "node:module";

// The installed react, not the range in package.json: the range can be "^19.2.8"
// while node_modules holds 19.4, and the plugin wants a concrete version.
const reactVersion = createRequire(import.meta.url)("react/package.json").version;

// Next 16 removed `next lint`, so `npm run lint` invokes the ESLint CLI directly
// (`eslint .`). eslint-config-next now ships flat configs as real entry points,
// so the old FlatCompat bridge is gone. Two consequences of driving the CLI
// ourselves instead of going through `next lint`:
//   1. `next lint` only ever walked app/, components/, and lib/. `eslint .`
//      walks everything, so e2e/, __tests__/, and the generated report dirs are
//      now in scope — handled explicitly below.
//   2. `next lint` supplied the ignore list implicitly; the generated dirs it
//      never walked are now ignored explicitly at the bottom.
const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    // eslint-config-next sets `settings.react.version = "detect"`, and detection
    // is the ONLY path that reaches eslint-plugin-react's `resolveBasedir`, which
    // calls `context.getFilename()` — removed in eslint 10. Pinning the version
    // explicitly skips detection entirely, which is what unblocks eslint 10 here
    // (#391). It is also just better: detection stats the filesystem once per
    // linted file to rediscover a version that is already on disk.
    //
    // READ, not hardcoded. A literal string here is a second place to remember on
    // every React bump, and the one nobody remembers — it would drift silently and
    // the plugin's version-gated rules would start answering for the wrong React.
    // This resolves the actually-installed version once, at config load.
    settings: { react: { version: reactVersion } },
    rules: {
      "@typescript-eslint/no-explicit-any": "warn",
      // Ban debug console output in shipped code; console.warn/error are allowed
      // for real diagnostics. Production bundles strip these anyway via
      // next.config removeConsole, but this keeps new debug logging out. (#288)
      "no-console": ["error", { allow: ["warn", "error"] }],
    },
  },
    {
    // Tests and setup may use console freely, and may use require() for the
    // lazy/isolated module loading that jest module-mocking needs. e2e/ is
    // Playwright test code plus its helpers and fixtures — same allowance, and
    // newly in scope now that the ESLint CLI walks the whole project.
    files: [
      "**/*.test.{ts,tsx}",
      "**/*.spec.{ts,tsx}",
      "**/__tests__/**",
      "e2e/**",
      "jest.setup.*",
      // Developer CLI checks. Printing IS the output — check:adapter (#344) is a
      // pass/fail report a human and CI both read off stdout.
      "scripts/**",
    ],
    rules: {
      "no-console": "off",
      "@typescript-eslint/no-require-imports": "off",
    },
  },
  {
    // Playwright fixtures take `use()` callbacks, which the React Hooks plugin
    // mistakes for React 19's `use()` hook and then applies rules-of-hooks to.
    // e2e/ contains no React, so the rule only ever produces false positives.
    files: ["e2e/**"],
    rules: {
      "react-hooks/rules-of-hooks": "off",
    },
  },
  {
    // CommonJS tooling config (jest.config.js loads next/jest via require).
    files: ["*.config.js"],
    rules: {
      "@typescript-eslint/no-require-imports": "off",
    },
  },
  globalIgnores([
    // eslint-config-next already ignores these four; flat-config ignore blocks
    // are cumulative, so listing them again is belt-and-braces, not a
    // requirement (verified: removing them still lints 0 files under .next/).
    // Kept so build output stays ignored even if upstream drops its defaults.
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // Generated artifacts that `next lint` never walked, and that
    // eslint-config-next does NOT ignore — these are load-bearing.
    "coverage/**",
    "playwright-report/**",
    "test-results/**",
    ".swc/**",
  ]),
]);

export default eslintConfig;
