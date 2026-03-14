import React from "react";

/**
 * Mock for react-markdown that renders children as plain HTML.
 * Converts basic markdown **bold** and [links](url) for testing.
 */
function ReactMarkdown({ children }: { children: string }) {
  // Convert **bold** to <strong>
  let html = children.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  // Convert [text](url) to <a>
  html = html.replace(
    /\[(.+?)\]\((.+?)\)/g,
    '<a href="$2">$1</a>'
  );
  return <div dangerouslySetInnerHTML={{ __html: html }} />;
}

export default ReactMarkdown;
