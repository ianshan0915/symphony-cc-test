"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export interface MessageSkeletonProps {
  /** Number of skeleton message pairs to show (default: 3) */
  count?: number;
  /** Additional class names */
  className?: string;
}

/**
 * MessageSkeleton — pulsing placeholder skeleton shown while a thread is loading.
 *
 * Mimics the visual structure of real message bubbles to reduce layout shift.
 */
export function MessageSkeleton({ count = 3, className }: MessageSkeletonProps) {
  return (
    <div
      className={cn("flex flex-col gap-4 p-4 max-w-2xl mx-auto w-full", className)}
      data-testid="message-skeleton"
    >
      {Array.from({ length: count }).map((_, i) => (
        <React.Fragment key={i}>
          {/* User message skeleton — right aligned */}
          <div className="flex justify-end gap-3">
            <div className="flex flex-col items-end gap-1.5">
              <div className="rounded-2xl rounded-br-md bg-primary/10 animate-pulse h-10 w-48" />
            </div>
            <div className="h-8 w-8 rounded-full bg-primary/10 animate-pulse shrink-0" />
          </div>

          {/* Assistant message skeleton — left aligned */}
          <div className="flex justify-start gap-3">
            <div className="h-8 w-8 rounded-full bg-secondary animate-pulse shrink-0" />
            <div className="flex flex-col gap-1.5">
              <div className="rounded-2xl rounded-bl-md bg-card border border-border animate-pulse h-16 w-72" />
              {/* Shorter second line */}
              {i === 0 && (
                <div className="rounded-lg bg-card border border-border animate-pulse h-8 w-40" />
              )}
            </div>
          </div>
        </React.Fragment>
      ))}
    </div>
  );
}
