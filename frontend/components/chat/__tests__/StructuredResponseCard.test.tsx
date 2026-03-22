import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { StructuredResponseCard } from "../StructuredResponseCard";

describe("StructuredResponseCard", () => {
  // ---------------------------------------------------------------------------
  // Basic rendering
  // ---------------------------------------------------------------------------

  it("renders the 'Structured Response' header label", () => {
    render(<StructuredResponseCard data={{ name: "Alice" }} />);
    expect(screen.getByText("Structured Response")).toBeInTheDocument();
  });

  it("renders with the expected test id", () => {
    render(<StructuredResponseCard data={{ key: "value" }} />);
    expect(screen.getByTestId("structured-response-card")).toBeInTheDocument();
  });

  // ---------------------------------------------------------------------------
  // Flat object — key-value table
  // ---------------------------------------------------------------------------

  it("renders human-readable labels for snake_case keys", () => {
    render(<StructuredResponseCard data={{ first_name: "Bob" }} />);
    expect(screen.getByText("First Name")).toBeInTheDocument();
  });

  it("renders human-readable labels for camelCase keys", () => {
    render(<StructuredResponseCard data={{ firstName: "Carol" }} />);
    expect(screen.getByText("First Name")).toBeInTheDocument();
  });

  it("renders string field values", () => {
    render(<StructuredResponseCard data={{ city: "London" }} />);
    expect(screen.getByText("London")).toBeInTheDocument();
  });

  it("renders integer values with locale formatting", () => {
    render(<StructuredResponseCard data={{ count: 42 }} />);
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("renders boolean true as 'Yes'", () => {
    render(<StructuredResponseCard data={{ active: true }} />);
    expect(screen.getByText("Yes")).toBeInTheDocument();
  });

  it("renders boolean false as 'No'", () => {
    render(<StructuredResponseCard data={{ active: false }} />);
    expect(screen.getByText("No")).toBeInTheDocument();
  });

  it("renders null values as em-dash", () => {
    render(<StructuredResponseCard data={{ missing: null }} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  // ---------------------------------------------------------------------------
  // URL values
  // ---------------------------------------------------------------------------

  it("renders URL strings as clickable links", () => {
    render(<StructuredResponseCard data={{ homepage: "https://example.com" }} />);
    const link = screen.getByRole("link", { name: "https://example.com" });
    expect(link).toHaveAttribute("href", "https://example.com");
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("renders URL links with rel=noopener noreferrer for security", () => {
    render(<StructuredResponseCard data={{ homepage: "https://example.com" }} />);
    const link = screen.getByRole("link", { name: "https://example.com" });
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("does not render non-URL strings as links", () => {
    render(<StructuredResponseCard data={{ description: "just a string" }} />);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  // ---------------------------------------------------------------------------
  // Date values
  // ---------------------------------------------------------------------------

  it("renders ISO date strings in human-readable form", () => {
    render(<StructuredResponseCard data={{ created_at: "2025-06-15T14:30:00Z" }} />);
    // Verify the raw ISO string is exposed via title attribute on the span
    const span = document.querySelector('[title="2025-06-15T14:30:00Z"]');
    expect(span).toBeInTheDocument();
  });

  it("does not render a plain year string as a date", () => {
    render(<StructuredResponseCard data={{ value: "2024" }} />);
    // Should render as plain text, not trigger date formatting (no title attribute)
    expect(document.querySelector('[title="2024"]')).not.toBeInTheDocument();
    expect(screen.getByText("2024")).toBeInTheDocument();
  });

  it("does not render a partial date string like '2025-06' as a date", () => {
    render(<StructuredResponseCard data={{ version: "2025-06" }} />);
    // Should NOT have a date title attribute — the ISO_DATE_RE requires YYYY-MM-DD
    expect(document.querySelector('[title="2025-06"]')).not.toBeInTheDocument();
  });

  // ---------------------------------------------------------------------------
  // Nested objects
  // ---------------------------------------------------------------------------

  it("renders nested object fields recursively", () => {
    render(
      <StructuredResponseCard
        data={{ address: { city: "Paris", country: "France" } }}
      />
    );
    expect(screen.getByText("City")).toBeInTheDocument();
    expect(screen.getByText("Paris")).toBeInTheDocument();
    expect(screen.getByText("Country")).toBeInTheDocument();
    expect(screen.getByText("France")).toBeInTheDocument();
  });

  it("renders empty nested object with placeholder", () => {
    render(<StructuredResponseCard data={{ metadata: {} }} />);
    expect(screen.getByText("(empty)")).toBeInTheDocument();
  });

  it("falls back to JSON for deeply nested structures beyond MAX_DEPTH", () => {
    // Build an object nested 10 levels deep (exceeds MAX_DEPTH of 8)
    let deep: Record<string, unknown> = { leaf: "value" };
    for (let i = 0; i < 10; i++) {
      deep = { nested: deep };
    }
    render(<StructuredResponseCard data={deep} />);
    // The deeply nested content should eventually hit the depth cap and render as <pre>
    const card = screen.getByTestId("structured-response-card");
    expect(card).toBeInTheDocument();
    // At some nesting level there should be a <pre> fallback
    const pre = card.querySelector("pre");
    expect(pre).toBeInTheDocument();
  });

  // ---------------------------------------------------------------------------
  // Array values
  // ---------------------------------------------------------------------------

  it("renders array items as a list", () => {
    render(<StructuredResponseCard data={{ tags: ["alpha", "beta", "gamma"] }} />);
    expect(screen.getByText("alpha")).toBeInTheDocument();
    expect(screen.getByText("beta")).toBeInTheDocument();
    expect(screen.getByText("gamma")).toBeInTheDocument();
  });

  it("renders empty arrays with a placeholder", () => {
    render(<StructuredResponseCard data={{ items: [] }} />);
    expect(screen.getByText("[ empty list ]")).toBeInTheDocument();
  });

  // ---------------------------------------------------------------------------
  // Fallback — non-object top-level data
  // ---------------------------------------------------------------------------

  it("falls back to formatted JSON for array data", () => {
    // @ts-expect-error intentionally passing wrong type to test fallback
    render(<StructuredResponseCard data={["a", "b"]} />);
    const card = screen.getByTestId("structured-response-card");
    const pre = card.querySelector("pre");
    expect(pre).toBeInTheDocument();
    expect(pre!.textContent).toContain('"a"');
  });

  // ---------------------------------------------------------------------------
  // Multiple fields — table structure
  // ---------------------------------------------------------------------------

  it("renders a table element for structured data", () => {
    render(
      <StructuredResponseCard data={{ name: "Alice", age: 30, city: "NYC" }} />
    );
    expect(screen.getByTestId("structured-table")).toBeInTheDocument();
  });

  it("renders all top-level keys", () => {
    render(
      <StructuredResponseCard data={{ alpha: "one", beta: "two", gamma: "three" }} />
    );
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Beta")).toBeInTheDocument();
    expect(screen.getByText("Gamma")).toBeInTheDocument();
  });
});
