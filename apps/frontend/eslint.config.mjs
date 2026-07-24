import { dirname } from "path";
import { fileURLToPath } from "url";
import { FlatCompat } from "@eslint/eslintrc";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const compat = new FlatCompat({
  baseDirectory: __dirname,
});

const eslintConfig = [
  ...compat.extends("next/core-web-vitals", "next/typescript"),
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
    // Tests and setup may use console freely.
    files: [
      "**/*.test.{ts,tsx}",
      "**/*.spec.{ts,tsx}",
      "**/__tests__/**",
      "jest.setup.*",
    ],
    rules: {
      "no-console": "off",
    },
  },
];

export default eslintConfig;
