import { dirname } from "path";
import { fileURLToPath } from "url";
import nextConfig from "eslint-config-next/core-web-vitals";

const __dirname = dirname(fileURLToPath(import.meta.url));

/** @type {import("eslint").Linter.Config[]} */
const config = [
  ...nextConfig,
  {
    settings: {
      next: {
        rootDir: __dirname,
      },
    },
  },
];

export default config;
