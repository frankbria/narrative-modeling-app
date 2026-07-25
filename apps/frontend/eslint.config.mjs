import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

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
    rules: {
      "@typescript-eslint/no-explicit-any": "warn",
      // Ban debug console output in shipped code; console.warn/error are allowed
      // for real diagnostics. Production bundles strip these anyway via
      // next.config removeConsole, but this keeps new debug logging out. (#288)
      "no-console": ["error", { allow: ["warn", "error"] }],
    },
  },
  {
    // React Compiler rules, new in eslint-plugin-react-hooks v7 — which arrives
    // transitively with eslint-config-next 16, not from any change in this app.
    // They flag 63 pre-existing patterns across app/, components/, and lib/;
    // clearing them is a state/effect refactor with real behavioral risk and no
    // relation to the framework bump, so they are demoted to warnings here to
    // keep them visible rather than switched off and forgotten. Promote back to
    // "error" as they are burned down. See follow-up issue #373.
    //
    // Demoting to "warn" would normally weaken the gate, so the lint script
    // pins --max-warnings to the current total: these cannot silently grow, and
    // the ceiling ratchets down as #373 lands.
    name: "react-compiler-rules-pending-burndown",
    rules: {
      "react-hooks/immutability": "warn",
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/static-components": "warn",
      "react-hooks/refs": "warn",
      "react-hooks/preserve-manual-memoization": "warn",
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
