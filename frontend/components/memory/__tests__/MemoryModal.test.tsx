import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { MemoryModal } from "../MemoryModal";

// ---------------------------------------------------------------------------
// fetch mock helpers
// ---------------------------------------------------------------------------

function mockFetch(handler: (url: string, init?: RequestInit) => unknown) {
  (global.fetch as jest.Mock).mockImplementation((url: string, init?: RequestInit) =>
    Promise.resolve(handler(url, init))
  );
}

function okJson(data: unknown) {
  return { ok: true, status: 200, json: async () => data };
}

function errorJson(status: number, detail: string) {
  return {
    ok: false,
    status,
    json: async () => ({ detail }),
    statusText: detail,
  };
}

beforeEach(() => {
  global.fetch = jest.fn();
  // Default: GET /memory succeeds
  mockFetch(() => okJson({ content: "" }));
  // Provide a fake token so Authorization header is set
  localStorage.setItem("symphony_token", "fake-token");
});

afterEach(() => {
  jest.restoreAllMocks();
  localStorage.clear();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("MemoryModal", () => {
  it("does not render content when closed", () => {
    render(<MemoryModal open={false} onClose={jest.fn()} />);
    // Radix Dialog does not mount content when closed
    expect(screen.queryByTestId("memory-modal")).not.toBeInTheDocument();
  });

  it("shows loading state while fetching", async () => {
    (global.fetch as jest.Mock).mockImplementation(
      () => new Promise(() => {}) // never resolves
    );
    render(<MemoryModal open onClose={jest.fn()} />);
    expect(await screen.findByText("Loading memory…")).toBeInTheDocument();
  });

  it("displays fetched memory content in textarea", async () => {
    const content = "# Agent Memory\n\nUser prefers TypeScript.";
    mockFetch(() => okJson({ content }));
    render(<MemoryModal open onClose={jest.fn()} />);

    const textarea = await screen.findByRole("textbox", {
      name: /agent memory content/i,
    });
    expect(textarea).toHaveValue(content);
  });

  it("shows error banner when fetch fails", async () => {
    (global.fetch as jest.Mock).mockRejectedValue(new Error("Network error"));
    render(<MemoryModal open onClose={jest.fn()} />);
    expect(
      await screen.findByText("Failed to load memory. Please try again.")
    ).toBeInTheDocument();
  });

  it("disables Save button when content is unchanged", async () => {
    mockFetch(() => okJson({ content: "# Memory" }));
    render(<MemoryModal open onClose={jest.fn()} />);

    await screen.findByRole("textbox");
    const saveBtn = screen.getByRole("button", { name: /save/i });
    expect(saveBtn).toBeDisabled();
  });

  it("enables Save and Reset buttons after editing", async () => {
    mockFetch(() => okJson({ content: "# Memory" }));
    render(<MemoryModal open onClose={jest.fn()} />);

    const textarea = await screen.findByRole("textbox", {
      name: /agent memory content/i,
    });
    await userEvent.clear(textarea);
    await userEvent.type(textarea, "New content");

    expect(screen.getByRole("button", { name: /save/i })).toBeEnabled();
    expect(screen.getByRole("button", { name: /reset/i })).toBeEnabled();
  });

  it("saves updated content when Save is clicked", async () => {
    const initial = "# Memory";
    const updated = "# Memory\n\nNew fact";
    let callCount = 0;
    (global.fetch as jest.Mock).mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        // Auth refresh attempt or GET
        return Promise.resolve(okJson({ content: initial }));
      }
      return Promise.resolve(okJson({ content: updated }));
    });

    render(<MemoryModal open onClose={jest.fn()} />);

    const textarea = await screen.findByRole("textbox", {
      name: /agent memory content/i,
    });
    await userEvent.clear(textarea);
    await userEvent.type(textarea, updated);
    await userEvent.click(screen.getByRole("button", { name: /save/i }));

    // Verify PUT was called
    await waitFor(() => {
      const calls = (global.fetch as jest.Mock).mock.calls;
      const putCall = calls.find(
        ([, init]: [string, RequestInit]) => init?.method === "PUT"
      );
      expect(putCall).toBeDefined();
    });

    // Success banner appears
    expect(
      await screen.findByText("Memory saved successfully.")
    ).toBeInTheDocument();
  });

  it("shows error banner when save fails", async () => {
    let callCount = 0;
    (global.fetch as jest.Mock).mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        return Promise.resolve(okJson({ content: "# Memory" }));
      }
      return Promise.resolve(errorJson(503, "Memory store unavailable"));
    });

    render(<MemoryModal open onClose={jest.fn()} />);

    const textarea = await screen.findByRole("textbox", {
      name: /agent memory content/i,
    });
    await userEvent.clear(textarea);
    await userEvent.type(textarea, "Changed");
    await userEvent.click(screen.getByRole("button", { name: /save/i }));

    expect(
      await screen.findByText("Memory store unavailable")
    ).toBeInTheDocument();
  });

  it("resets content to last saved state when Reset is clicked", async () => {
    const original = "# Memory";
    mockFetch(() => okJson({ content: original }));
    render(<MemoryModal open onClose={jest.fn()} />);

    const textarea = await screen.findByRole("textbox", {
      name: /agent memory content/i,
    });
    await userEvent.clear(textarea);
    await userEvent.type(textarea, "Different content");
    await userEvent.click(screen.getByRole("button", { name: /reset/i }));

    expect(textarea).toHaveValue(original);
  });

  it("displays byte counter", async () => {
    mockFetch(() => okJson({ content: "Hello" }));
    render(<MemoryModal open onClose={jest.fn()} />);

    await screen.findByRole("textbox");
    expect(screen.getByText(/\/ 512 KiB/)).toBeInTheDocument();
  });

  it("calls onClose when dialog close button is clicked", async () => {
    mockFetch(() => okJson({ content: "# Memory" }));
    const onClose = jest.fn();
    render(<MemoryModal open onClose={onClose} />);

    await screen.findByRole("textbox");

    // Radix Dialog includes a close button with sr-only text "Close"
    const closeBtn = screen.getByRole("button", { name: /close/i });
    await userEvent.click(closeBtn);

    expect(onClose).toHaveBeenCalled();
  });
});
