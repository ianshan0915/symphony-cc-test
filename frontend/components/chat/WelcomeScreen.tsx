"use client";

import * as React from "react";
import { Search, Code2, FileText, Lightbulb } from "lucide-react";
import { cn } from "@/lib/utils";

export interface WelcomeScreenProps {
  /** Called when user clicks a starter prompt card */
  onSend: (message: string) => void;
  /** Additional class names */
  className?: string;
}

interface StarterPrompt {
  icon: React.ElementType;
  iconColor: string;
  title: string;
  message: string;
}

const starterPrompts: StarterPrompt[] = [
  {
    icon: Search,
    iconColor: "text-blue-500",
    title: "Search the web for latest AI news",
    message: "Search the web for the latest AI news and give me a summary of the top stories.",
  },
  {
    icon: Code2,
    iconColor: "text-green-500",
    title: "Write a Python function to sort a list",
    message: "Write a Python function that sorts a list of dictionaries by a given key, with support for ascending and descending order.",
  },
  {
    icon: FileText,
    iconColor: "text-orange-500",
    title: "Help me draft a professional email",
    message: "Help me draft a professional email to my team announcing a new project timeline. Keep it concise and positive.",
  },
  {
    icon: Lightbulb,
    iconColor: "text-purple-500",
    title: "Explain how machine learning works",
    message: "Explain how machine learning works in simple terms, with a real-world example. Assume I have no technical background.",
  },
];

/**
 * WelcomeScreen — displayed when there are no messages.
 *
 * Shows a welcome message and 4 clickable starter prompt cards in a 2×2 grid.
 * Clicking a card auto-sends the associated message.
 */
export function WelcomeScreen({ onSend, className }: WelcomeScreenProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-12 px-4",
        className
      )}
      data-testid="welcome-screen"
    >
      {/* Welcome heading */}
      <div className="text-center mb-8">
        <h2 className="text-2xl font-semibold text-foreground mb-2">
          ✨ Welcome to Symphony
        </h2>
        <p className="text-sm text-muted-foreground max-w-md">
          Your AI assistant that can search the web, write code, and help you think.
        </p>
      </div>

      {/* Starter prompt grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-lg">
        {starterPrompts.map((prompt) => (
          <button
            key={prompt.title}
            type="button"
            onClick={() => onSend(prompt.message)}
            className={cn(
              "flex items-start gap-3 rounded-xl border border-border bg-card p-4 text-left",
              "hover:bg-accent/50 hover:border-border/80 transition-colors",
              "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
              "group cursor-pointer"
            )}
          >
            <prompt.icon
              className={cn("h-5 w-5 shrink-0 mt-0.5", prompt.iconColor)}
            />
            <span className="text-sm text-foreground leading-snug group-hover:text-foreground/90">
              {prompt.title}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
