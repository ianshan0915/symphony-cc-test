const nextJest = require("next/jest.js");

const createJestConfig = nextJest({
  dir: "./",
});

/** @type {import('jest').Config} */
const config = {
  coverageProvider: "v8",
  testEnvironment: "jsdom",
  setupFilesAfterEnv: ["<rootDir>/jest.setup.ts"],
  moduleNameMapper: {
    "^react-markdown$": "<rootDir>/__mocks__/react-markdown.tsx",
    "^remark-gfm$": "<rootDir>/__mocks__/remark-gfm.ts",
  },
};

module.exports = createJestConfig(config);
