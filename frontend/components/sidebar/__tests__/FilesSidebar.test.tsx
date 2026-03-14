import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { FilesSidebar } from "../FilesSidebar";
import type { FileOperation } from "@/lib/types";

const mockFiles: FileOperation[] = [
  {
    id: "f1",
    operation: "read",
    filePath: "/src/components/App.tsx",
    toolName: "read_file",
    status: "completed",
    timestamp: new Date().toISOString(),
    preview: "import React from 'react';",
  },
  {
    id: "f2",
    operation: "write",
    filePath: "/src/utils/helpers.ts",
    toolName: "write_file",
    status: "completed",
    timestamp: new Date().toISOString(),
  },
  {
    id: "f3",
    operation: "create",
    filePath: "/src/new-file.ts",
    toolName: "create_file",
    status: "pending",
    timestamp: new Date().toISOString(),
  },
];

describe("FilesSidebar", () => {
  it("renders empty state when no files", () => {
    render(<FilesSidebar files={[]} />);
    expect(screen.getByText("No file operations yet")).toBeInTheDocument();
    expect(
      screen.getByText("File reads and writes will appear here")
    ).toBeInTheDocument();
  });

  it("renders file list with correct count", () => {
    render(<FilesSidebar files={mockFiles} />);
    expect(screen.getByText("File Operations")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument(); // total count
  });

  it("shows file names", () => {
    render(<FilesSidebar files={mockFiles} />);
    expect(screen.getByText("App.tsx")).toBeInTheDocument();
    expect(screen.getByText("helpers.ts")).toBeInTheDocument();
    expect(screen.getByText("new-file.ts")).toBeInTheDocument();
  });

  it("shows summary badges", () => {
    render(<FilesSidebar files={mockFiles} />);
    expect(screen.getByText("1 read")).toBeInTheDocument();
    expect(screen.getByText("2 written")).toBeInTheDocument();
  });

  it("shows operation labels", () => {
    render(<FilesSidebar files={mockFiles} />);
    expect(screen.getByText("Read")).toBeInTheDocument();
    expect(screen.getByText("Modified")).toBeInTheDocument();
    expect(screen.getByText("Created")).toBeInTheDocument();
  });

  it("expands to show preview on click", async () => {
    render(<FilesSidebar files={mockFiles} />);

    // The first file has a preview
    const fileItem = screen.getByText("App.tsx").closest("[role='button']");
    expect(fileItem).toBeInTheDocument();

    if (fileItem) {
      await userEvent.click(fileItem);
      expect(
        screen.getByText("import React from 'react';")
      ).toBeInTheDocument();
    }
  });
});
